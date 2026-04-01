"""
Project Aura - Neural Memory Audit Tests

Tests for the neural memory audit logging system that provides
comprehensive audit logging for neural memory operations.
"""

import json
from datetime import datetime

from src.services.neural_memory_audit import (
    AuditEventType,
    AuditRecord,
    AuditSeverity,
    FileAuditStorage,
    InMemoryAuditStorage,
    NeuralMemoryAuditLogger,
)


class TestAuditEventType:
    """Tests for AuditEventType enum."""

    def test_memory_update(self):
        """Test memory update event type."""
        assert AuditEventType.MEMORY_UPDATE.value == "memory_update"

    def test_memory_retrieve(self):
        """Test memory retrieve event type."""
        assert AuditEventType.MEMORY_RETRIEVE.value == "memory_retrieve"

    def test_memory_consolidation(self):
        """Test memory consolidation event type."""
        assert AuditEventType.MEMORY_CONSOLIDATION.value == "memory_consolidation"

    def test_ttt_training(self):
        """Test TTT training event type."""
        assert AuditEventType.TTT_TRAINING.value == "ttt_training"

    def test_size_limit_warning(self):
        """Test size limit warning event type."""
        assert AuditEventType.SIZE_LIMIT_WARNING.value == "size_limit_warning"

    def test_size_limit_exceeded(self):
        """Test size limit exceeded event type."""
        assert AuditEventType.SIZE_LIMIT_EXCEEDED.value == "size_limit_exceeded"

    def test_checkpoint_save(self):
        """Test checkpoint save event type."""
        assert AuditEventType.CHECKPOINT_SAVE.value == "checkpoint_save"

    def test_checkpoint_load(self):
        """Test checkpoint load event type."""
        assert AuditEventType.CHECKPOINT_LOAD.value == "checkpoint_load"

    def test_service_init(self):
        """Test service init event type."""
        assert AuditEventType.SERVICE_INIT.value == "service_init"

    def test_service_shutdown(self):
        """Test service shutdown event type."""
        assert AuditEventType.SERVICE_SHUTDOWN.value == "service_shutdown"

    def test_config_change(self):
        """Test config change event type."""
        assert AuditEventType.CONFIG_CHANGE.value == "config_change"

    def test_error(self):
        """Test error event type."""
        assert AuditEventType.ERROR.value == "error"

    def test_all_event_types_exist(self):
        """Test all expected event types exist."""
        event_types = list(AuditEventType)
        assert len(event_types) == 12


class TestAuditSeverity:
    """Tests for AuditSeverity enum."""

    def test_info(self):
        """Test info severity."""
        assert AuditSeverity.INFO.value == "info"

    def test_warning(self):
        """Test warning severity."""
        assert AuditSeverity.WARNING.value == "warning"

    def test_error(self):
        """Test error severity."""
        assert AuditSeverity.ERROR.value == "error"

    def test_critical(self):
        """Test critical severity."""
        assert AuditSeverity.CRITICAL.value == "critical"


class TestAuditRecord:
    """Tests for AuditRecord dataclass."""

    def test_default_record(self):
        """Test default record creation."""
        record = AuditRecord()
        assert record.event_type == AuditEventType.MEMORY_UPDATE
        assert record.severity == AuditSeverity.INFO
        assert record.service_name == "TitanMemoryService"
        assert record.actor == "system"
        assert record.environment == "dev"

    def test_record_has_event_id(self):
        """Test record has auto-generated event ID."""
        record = AuditRecord()
        assert record.event_id is not None
        assert len(record.event_id) > 0

    def test_record_has_timestamp(self):
        """Test record has auto-generated timestamp."""
        record = AuditRecord()
        assert record.timestamp is not None
        # Should be ISO format
        datetime.fromisoformat(record.timestamp.replace("Z", "+00:00"))

    def test_record_has_checksum(self):
        """Test record has auto-generated checksum."""
        record = AuditRecord()
        assert record.checksum is not None
        assert len(record.checksum) == 16

    def test_custom_record(self):
        """Test custom record creation."""
        record = AuditRecord(
            event_type=AuditEventType.MEMORY_RETRIEVE,
            severity=AuditSeverity.WARNING,
            operation="test_operation",
            actor="agent-123",
            resource="memory-module-1",
            details={"key": "value"},
            memory_size_mb=45.5,
            surprise_score=0.85,
            was_memorized=True,
            ttt_steps=3,
            latency_ms=15.2,
            correlation_id="corr-123",
            environment="prod",
        )
        assert record.event_type == AuditEventType.MEMORY_RETRIEVE
        assert record.actor == "agent-123"
        assert record.memory_size_mb == 45.5
        assert record.surprise_score == 0.85
        assert record.was_memorized is True

    def test_to_dict(self):
        """Test to_dict conversion."""
        record = AuditRecord(
            event_type=AuditEventType.ERROR,
            severity=AuditSeverity.ERROR,
            operation="test",
        )
        data = record.to_dict()

        assert data["event_type"] == "error"
        assert data["severity"] == "error"
        assert "event_id" in data
        assert "timestamp" in data

    def test_to_json(self):
        """Test to_json conversion."""
        record = AuditRecord()
        json_str = record.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert "event_id" in data

    def test_verify_integrity_valid(self):
        """Test integrity verification on valid record."""
        record = AuditRecord(operation="test")
        assert record.verify_integrity() is True

    def test_verify_integrity_tampered(self):
        """Test integrity verification on tampered record."""
        record = AuditRecord(operation="test")
        # Tamper with the record
        record.operation = "tampered"
        # Checksum should no longer match
        assert record.verify_integrity() is False

    def test_checksum_deterministic(self):
        """Test checksum is deterministic for same data."""
        record1 = AuditRecord(
            event_id="test-id",
            timestamp="2025-01-01T00:00:00+00:00",
            operation="test",
        )
        record2 = AuditRecord(
            event_id="test-id",
            timestamp="2025-01-01T00:00:00+00:00",
            operation="test",
        )
        # Same data should produce same checksum
        # (Note: checksum computed from content, not existing checksum)
        assert record1._compute_checksum() == record2._compute_checksum()


class TestInMemoryAuditStorage:
    """Tests for InMemoryAuditStorage class."""

    def test_init_default(self):
        """Test default initialization."""
        storage = InMemoryAuditStorage()
        assert storage.max_records == 10000
        assert len(storage._records) == 0

    def test_init_custom_max(self):
        """Test custom max records."""
        storage = InMemoryAuditStorage(max_records=100)
        assert storage.max_records == 100

    def test_store_record(self):
        """Test storing a record."""
        storage = InMemoryAuditStorage()
        record = AuditRecord(operation="test")

        result = storage.store(record)

        assert result is True
        assert len(storage._records) == 1

    def test_store_multiple_records(self):
        """Test storing multiple records."""
        storage = InMemoryAuditStorage()

        for i in range(5):
            storage.store(AuditRecord(operation=f"test-{i}"))

        assert len(storage._records) == 5

    def test_store_batch(self):
        """Test batch storage."""
        storage = InMemoryAuditStorage()
        records = [AuditRecord(operation=f"test-{i}") for i in range(10)]

        count = storage.store_batch(records)

        assert count == 10
        assert len(storage._records) == 10

    def test_max_records_limit(self):
        """Test max records limit is enforced."""
        storage = InMemoryAuditStorage(max_records=5)

        for i in range(10):
            storage.store(AuditRecord(operation=f"test-{i}"))

        assert len(storage._records) == 5
        # Should keep latest records
        assert storage._records[-1].operation == "test-9"

    def test_query_all(self):
        """Test querying all records."""
        storage = InMemoryAuditStorage()
        for i in range(3):
            storage.store(AuditRecord(operation=f"test-{i}"))

        results = storage.query()

        assert len(results) == 3

    def test_query_by_event_type(self):
        """Test querying by event type."""
        storage = InMemoryAuditStorage()
        storage.store(AuditRecord(event_type=AuditEventType.MEMORY_UPDATE))
        storage.store(AuditRecord(event_type=AuditEventType.ERROR))
        storage.store(AuditRecord(event_type=AuditEventType.MEMORY_UPDATE))

        results = storage.query(event_type=AuditEventType.MEMORY_UPDATE)

        assert len(results) == 2

    def test_query_by_correlation_id(self):
        """Test querying by correlation ID."""
        storage = InMemoryAuditStorage()
        storage.store(AuditRecord(correlation_id="corr-1"))
        storage.store(AuditRecord(correlation_id="corr-2"))
        storage.store(AuditRecord(correlation_id="corr-1"))

        results = storage.query(correlation_id="corr-1")

        assert len(results) == 2

    def test_query_with_limit(self):
        """Test querying with limit."""
        storage = InMemoryAuditStorage()
        for i in range(10):
            storage.store(AuditRecord(operation=f"test-{i}"))

        results = storage.query(limit=3)

        assert len(results) == 3

    def test_clear(self):
        """Test clearing all records."""
        storage = InMemoryAuditStorage()
        for i in range(5):
            storage.store(AuditRecord())

        storage.clear()

        assert len(storage._records) == 0

    def test_get_all(self):
        """Test getting all records."""
        storage = InMemoryAuditStorage()
        for i in range(3):
            storage.store(AuditRecord(operation=f"test-{i}"))

        all_records = storage.get_all()

        assert len(all_records) == 3


class TestNeuralMemoryAuditLogger:
    """Tests for NeuralMemoryAuditLogger class."""

    def test_init_default(self):
        """Test default initialization."""
        logger = NeuralMemoryAuditLogger()

        assert logger.environment == "dev"
        assert logger.batch_size == 100
        assert logger.auto_flush is True
        assert isinstance(logger.storage, InMemoryAuditStorage)

    def test_init_custom(self):
        """Test custom initialization."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(
            storage=storage,
            environment="prod",
            batch_size=50,
            auto_flush=False,
        )

        assert logger.environment == "prod"
        assert logger.batch_size == 50
        assert logger.auto_flush is False

    def test_set_correlation_id(self):
        """Test setting correlation ID."""
        logger = NeuralMemoryAuditLogger()
        logger.set_correlation_id("corr-123")

        assert logger._current_correlation_id == "corr-123"

    def test_clear_correlation_id(self):
        """Test clearing correlation ID."""
        logger = NeuralMemoryAuditLogger()
        logger.set_correlation_id("corr-123")
        logger.clear_correlation_id()

        assert logger._current_correlation_id is None

    def test_log_memory_update(self):
        """Test logging memory update."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        event_id = logger.log_memory_update(
            actor="agent-123",
            surprise_score=0.85,
            was_memorized=True,
            ttt_steps=3,
            latency_ms=15.2,
            memory_size_mb=45.0,
        )

        assert event_id is not None
        assert len(logger._pending) == 1

    def test_log_memory_retrieve(self):
        """Test logging memory retrieve."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        event_id = logger.log_memory_retrieve(
            actor="agent-456",
            surprise_score=0.5,
            latency_ms=10.0,
        )

        assert event_id is not None
        assert logger._pending[0].event_type == AuditEventType.MEMORY_RETRIEVE

    def test_log_consolidation(self):
        """Test logging consolidation."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        event_id = logger.log_consolidation(
            records_consolidated=100,
            memory_before_mb=50.0,
            memory_after_mb=40.0,
            latency_ms=200.0,
        )

        assert event_id is not None
        assert logger._pending[0].event_type == AuditEventType.MEMORY_CONSOLIDATION

    def test_log_size_limit_warning(self):
        """Test logging size limit warning."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        event_id = logger.log_size_limit_warning(
            current_size_mb=90.0,
            max_size_mb=100.0,
            utilization_percent=90.0,
        )

        assert event_id is not None
        assert logger._pending[0].severity == AuditSeverity.WARNING

    def test_log_size_limit_exceeded(self):
        """Test logging size limit exceeded."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        event_id = logger.log_size_limit_exceeded(
            current_size_mb=110.0,
            max_size_mb=100.0,
            action_taken="consolidation_triggered",
        )

        assert event_id is not None
        assert logger._pending[0].severity == AuditSeverity.CRITICAL

    def test_log_service_init(self):
        """Test logging service initialization."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        event_id = logger.log_service_init(
            config={"memory_dim": 512, "depth": 3},
            memory_size_mb=0.0,
        )

        assert event_id is not None
        assert logger._pending[0].event_type == AuditEventType.SERVICE_INIT

    def test_log_service_shutdown(self):
        """Test logging service shutdown."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        event_id = logger.log_service_shutdown(
            stats={"total_updates": 1000, "total_retrieves": 500}
        )

        assert event_id is not None
        assert logger._pending[0].event_type == AuditEventType.SERVICE_SHUTDOWN

    def test_log_checkpoint_save(self):
        """Test logging checkpoint save."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        event_id = logger.log_checkpoint_save(
            path="/checkpoints/memory_v1.pt",
            memory_size_mb=50.0,
        )

        assert event_id is not None
        assert logger._pending[0].event_type == AuditEventType.CHECKPOINT_SAVE

    def test_log_checkpoint_load(self):
        """Test logging checkpoint load."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        event_id = logger.log_checkpoint_load(
            path="/checkpoints/memory_v1.pt",
            memory_size_mb=50.0,
        )

        assert event_id is not None
        assert logger._pending[0].event_type == AuditEventType.CHECKPOINT_LOAD

    def test_log_error(self):
        """Test logging error."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        event_id = logger.log_error(
            operation="update",
            error_message="Memory allocation failed",
            error_type="MemoryError",
        )

        assert event_id is not None
        assert logger._pending[0].event_type == AuditEventType.ERROR
        assert logger._error_count == 1

    def test_flush(self):
        """Test flushing pending records."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        for i in range(5):
            logger.log_memory_update(actor=f"agent-{i}")

        stored = logger.flush()

        assert stored == 5
        assert len(logger._pending) == 0
        assert len(storage._records) == 5

    def test_auto_flush(self):
        """Test auto-flush when batch size reached."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(
            storage=storage,
            batch_size=3,
            auto_flush=True,
        )

        for i in range(5):
            logger.log_memory_update(actor=f"agent-{i}")

        # Should have auto-flushed at 3
        assert len(storage._records) >= 3

    def test_get_stats(self):
        """Test getting stats."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        logger.log_memory_update()
        logger.log_error("test", "error")

        stats = logger.get_stats()

        assert stats["record_count"] == 2
        assert stats["error_count"] == 1
        assert stats["pending_count"] == 2
        assert stats["environment"] == "dev"

    def test_query(self):
        """Test querying through logger."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        logger.log_memory_update(actor="agent-1")
        logger.log_error("test", "error")

        # Query flushes first
        results = logger.query(event_type=AuditEventType.ERROR)

        assert len(results) == 1
        assert len(logger._pending) == 0

    def test_correlation_id_propagation(self):
        """Test correlation ID is added to records."""
        storage = InMemoryAuditStorage()
        logger = NeuralMemoryAuditLogger(storage=storage, auto_flush=False)

        logger.set_correlation_id("corr-123")
        logger.log_memory_update()
        logger.log_memory_retrieve()

        assert logger._pending[0].correlation_id == "corr-123"
        assert logger._pending[1].correlation_id == "corr-123"


class TestFileAuditStorage:
    """Tests for FileAuditStorage class."""

    def test_init(self):
        """Test initialization."""
        storage = FileAuditStorage(
            base_path="/tmp/audit-test",
            rotate_size_mb=50.0,
            environment="test",
        )
        assert storage.rotate_size_mb == 50.0
        assert storage.environment == "test"
