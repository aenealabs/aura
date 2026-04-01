"""Neural Memory Audit Logging for Production Compliance.

This module provides comprehensive audit logging for neural memory operations,
designed to meet enterprise compliance requirements (CMMC Level 3, SOX, NIST).

Key features:
1. Structured audit records with full context
2. Immutable audit trail
3. Support for multiple storage backends (file, DynamoDB)
4. Compliance-ready format with correlation IDs

Reference: ADR-024 - Titan Neural Memory Architecture Integration (Phase 5)
"""

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of auditable neural memory events."""

    MEMORY_UPDATE = "memory_update"
    MEMORY_RETRIEVE = "memory_retrieve"
    MEMORY_CONSOLIDATION = "memory_consolidation"
    TTT_TRAINING = "ttt_training"
    SIZE_LIMIT_WARNING = "size_limit_warning"
    SIZE_LIMIT_EXCEEDED = "size_limit_exceeded"
    CHECKPOINT_SAVE = "checkpoint_save"
    CHECKPOINT_LOAD = "checkpoint_load"
    SERVICE_INIT = "service_init"
    SERVICE_SHUTDOWN = "service_shutdown"
    CONFIG_CHANGE = "config_change"
    ERROR = "error"


class AuditSeverity(Enum):
    """Severity levels for audit events."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditRecord:
    """Structured audit record for neural memory operations.

    Attributes:
        event_id: Unique identifier for this audit event
        timestamp: ISO 8601 timestamp
        event_type: Type of auditable event
        severity: Event severity level
        service_name: Name of the service (e.g., TitanMemoryService)
        operation: Specific operation performed
        actor: Who/what initiated the operation (agent_id, session_id, etc.)
        resource: Resource affected (memory module, checkpoint path, etc.)
        details: Additional operation-specific details
        memory_size_mb: Memory size at time of event
        surprise_score: Neural surprise score (if applicable)
        was_memorized: Whether input was memorized (if applicable)
        ttt_steps: Number of TTT steps (if applicable)
        latency_ms: Operation latency in milliseconds
        correlation_id: ID to correlate related events
        parent_event_id: Parent event ID for hierarchical tracking
        environment: Environment (dev, staging, prod)
        checksum: SHA256 checksum of record for integrity verification
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    event_type: AuditEventType = AuditEventType.MEMORY_UPDATE
    severity: AuditSeverity = AuditSeverity.INFO
    service_name: str = "TitanMemoryService"
    operation: str = ""
    actor: str = "system"
    resource: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    memory_size_mb: float = 0.0
    surprise_score: Optional[float] = None
    was_memorized: bool = False
    ttt_steps: int = 0
    latency_ms: float = 0.0
    correlation_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    environment: str = "dev"
    checksum: str = ""

    def __post_init__(self) -> None:
        """Compute checksum after initialization."""
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """Compute SHA256 checksum for integrity verification."""
        # Create a copy without checksum for hashing
        data = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": (
                self.event_type.value
                if isinstance(self.event_type, AuditEventType)
                else self.event_type
            ),
            "severity": (
                self.severity.value
                if isinstance(self.severity, AuditSeverity)
                else self.severity
            ),
            "service_name": self.service_name,
            "operation": self.operation,
            "actor": self.actor,
            "resource": self.resource,
            "details": self.details,
            "memory_size_mb": self.memory_size_mb,
            "surprise_score": self.surprise_score,
            "was_memorized": self.was_memorized,
            "ttt_steps": self.ttt_steps,
            "latency_ms": self.latency_ms,
            "correlation_id": self.correlation_id,
            "parent_event_id": self.parent_event_id,
            "environment": self.environment,
        }
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to values
        data["event_type"] = (
            self.event_type.value
            if isinstance(self.event_type, AuditEventType)
            else self.event_type
        )
        data["severity"] = (
            self.severity.value
            if isinstance(self.severity, AuditSeverity)
            else self.severity
        )
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    def verify_integrity(self) -> bool:
        """Verify record integrity via checksum."""
        expected = self._compute_checksum()
        return self.checksum == expected


class AuditStorageBackend:
    """Base class for audit storage backends."""

    def store(self, record: AuditRecord) -> bool:
        """Store an audit record. Returns True on success."""
        raise NotImplementedError

    def store_batch(self, records: List[AuditRecord]) -> int:
        """Store multiple records. Returns number of successful stores."""
        raise NotImplementedError

    def query(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """Query audit records."""
        raise NotImplementedError


class FileAuditStorage(AuditStorageBackend):
    """File-based audit storage backend.

    Stores audit records as JSON Lines (one JSON object per line).
    Suitable for development and small-scale deployments.
    """

    def __init__(
        self,
        base_path: str = "/var/log/aura/neural-memory-audit",
        rotate_size_mb: float = 100.0,
        environment: str = "dev",
    ):
        """Initialize file audit storage.

        Args:
            base_path: Base directory for audit logs
            rotate_size_mb: Max file size before rotation
            environment: Environment name for file naming
        """
        self.base_path = Path(base_path)
        self.rotate_size_mb = rotate_size_mb
        self.environment = environment
        self._current_file: Optional[Path] = None
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure audit directory exists."""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create audit directory {self.base_path}: {e}")

    def _get_current_file(self) -> Path:
        """Get current log file path, rotating if needed."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"neural-memory-audit-{self.environment}-{today}.jsonl"
        file_path = self.base_path / filename

        # Check if rotation needed
        if file_path.exists():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb >= self.rotate_size_mb:
                # Rotate with timestamp
                timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
                rotated = (
                    f"neural-memory-audit-{self.environment}-{today}-{timestamp}.jsonl"
                )
                file_path.rename(self.base_path / rotated)
                logger.info(f"Rotated audit log to {rotated}")

        return file_path

    def store(self, record: AuditRecord) -> bool:
        """Store an audit record."""
        try:
            file_path = self._get_current_file()
            with open(file_path, "a") as f:
                f.write(record.to_json().replace("\n", " ") + "\n")
            return True
        except Exception as e:
            logger.error(f"Failed to store audit record: {e}")
            return False

    def store_batch(self, records: List[AuditRecord]) -> int:
        """Store multiple records."""
        success_count = 0
        try:
            file_path = self._get_current_file()
            with open(file_path, "a") as f:
                for record in records:
                    try:
                        f.write(record.to_json().replace("\n", " ") + "\n")
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to write audit record: {e}")
        except Exception as e:
            logger.error(f"Failed to open audit file: {e}")
        return success_count

    def query(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """Query audit records from file storage."""
        results: List[AuditRecord] = []

        try:
            # Find relevant files
            files = sorted(self.base_path.glob("*.jsonl"), reverse=True)

            for file_path in files:
                if len(results) >= limit:
                    break

                with open(file_path, "r") as f:
                    for line in f:
                        if len(results) >= limit:
                            break

                        try:
                            data = json.loads(line.strip())
                            record = AuditRecord(**data)

                            # Apply filters
                            if start_time and record.timestamp < start_time:
                                continue
                            if end_time and record.timestamp > end_time:
                                continue
                            if event_type and record.event_type != event_type.value:
                                continue
                            if (
                                correlation_id
                                and record.correlation_id != correlation_id
                            ):
                                continue

                            results.append(record)
                        except Exception as e:
                            logger.warning(f"Failed to parse audit line: {e}")

        except Exception as e:
            logger.error(f"Failed to query audit records: {e}")

        return results


class InMemoryAuditStorage(AuditStorageBackend):
    """In-memory audit storage for testing and development."""

    def __init__(self, max_records: int = 10000) -> None:
        """Initialize in-memory storage.

        Args:
            max_records: Maximum records to keep
        """
        self.max_records = max_records
        self._records: List[AuditRecord] = []

    def store(self, record: AuditRecord) -> bool:
        """Store an audit record."""
        self._records.append(record)
        if len(self._records) > self.max_records:
            self._records = self._records[-self.max_records :]
        return True

    def store_batch(self, records: List[AuditRecord]) -> int:
        """Store multiple records."""
        for record in records:
            self.store(record)
        return len(records)

    def query(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """Query audit records."""
        results: List[AuditRecord] = []
        for record in reversed(self._records):
            if len(results) >= limit:
                break

            # Apply filters
            if start_time and record.timestamp < start_time:
                continue
            if end_time and record.timestamp > end_time:
                continue
            if event_type:
                record_type = (
                    record.event_type
                    if isinstance(record.event_type, str)
                    else record.event_type.value
                )
                if record_type != event_type.value:
                    continue
            if correlation_id and record.correlation_id != correlation_id:
                continue

            results.append(record)

        return results

    def clear(self) -> None:
        """Clear all records."""
        self._records = []

    def get_all(self) -> List[AuditRecord]:
        """Get all stored records."""
        return list(self._records)


class NeuralMemoryAuditLogger:
    """Comprehensive audit logger for neural memory operations.

    Provides structured audit logging with:
    - Automatic correlation tracking
    - Integrity verification
    - Multiple storage backend support
    - Compliance-ready format

    Usage:
        ```python
        # Create audit logger
        audit = NeuralMemoryAuditLogger(
            storage=FileAuditStorage(base_path="/var/log/aura"),
            environment="prod",
        )

        # Log an operation
        audit.log_memory_update(
            actor="agent-123",
            surprise_score=0.85,
            was_memorized=True,
            ttt_steps=3,
            latency_ms=15.2,
            memory_size_mb=45.0,
            details={"task": "security_analysis"},
        )

        # Flush pending records
        audit.flush()
        ```
    """

    def __init__(
        self,
        storage: Optional[AuditStorageBackend] = None,
        environment: str = "dev",
        batch_size: int = 100,
        auto_flush: bool = True,
    ):
        """Initialize audit logger.

        Args:
            storage: Storage backend (defaults to InMemoryAuditStorage)
            environment: Environment name
            batch_size: Number of records before auto-flush
            auto_flush: Whether to auto-flush when batch_size reached
        """
        self.storage = storage or InMemoryAuditStorage()
        self.environment = environment
        self.batch_size = batch_size
        self.auto_flush = auto_flush

        self._pending: List[AuditRecord] = []
        self._current_correlation_id: Optional[str] = None
        self._record_count = 0
        self._error_count = 0

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set correlation ID for subsequent records."""
        self._current_correlation_id = correlation_id

    def clear_correlation_id(self) -> None:
        """Clear correlation ID."""
        self._current_correlation_id = None

    def _create_record(
        self,
        event_type: AuditEventType,
        operation: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        actor: str = "system",
        resource: str = "",
        details: Optional[Dict[str, Any]] = None,
        memory_size_mb: float = 0.0,
        surprise_score: Optional[float] = None,
        was_memorized: bool = False,
        ttt_steps: int = 0,
        latency_ms: float = 0.0,
        parent_event_id: Optional[str] = None,
    ) -> AuditRecord:
        """Create an audit record."""
        return AuditRecord(
            event_type=event_type,
            severity=severity,
            operation=operation,
            actor=actor,
            resource=resource,
            details=details or {},
            memory_size_mb=memory_size_mb,
            surprise_score=surprise_score,
            was_memorized=was_memorized,
            ttt_steps=ttt_steps,
            latency_ms=latency_ms,
            correlation_id=self._current_correlation_id,
            parent_event_id=parent_event_id,
            environment=self.environment,
        )

    def _add_record(self, record: AuditRecord) -> None:
        """Add record to pending queue."""
        self._pending.append(record)
        self._record_count += 1

        if self.auto_flush and len(self._pending) >= self.batch_size:
            self.flush()

    def log_memory_update(
        self,
        actor: str = "system",
        surprise_score: float = 0.0,
        was_memorized: bool = False,
        ttt_steps: int = 0,
        latency_ms: float = 0.0,
        memory_size_mb: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a memory update operation.

        Returns:
            Event ID of the created record
        """
        record = self._create_record(
            event_type=AuditEventType.MEMORY_UPDATE,
            operation="update",
            actor=actor,
            resource="neural_memory",
            surprise_score=surprise_score,
            was_memorized=was_memorized,
            ttt_steps=ttt_steps,
            latency_ms=latency_ms,
            memory_size_mb=memory_size_mb,
            details=details,
        )
        self._add_record(record)
        return record.event_id

    def log_memory_retrieve(
        self,
        actor: str = "system",
        surprise_score: float = 0.0,
        latency_ms: float = 0.0,
        memory_size_mb: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a memory retrieval operation.

        Returns:
            Event ID of the created record
        """
        record = self._create_record(
            event_type=AuditEventType.MEMORY_RETRIEVE,
            operation="retrieve",
            actor=actor,
            resource="neural_memory",
            surprise_score=surprise_score,
            latency_ms=latency_ms,
            memory_size_mb=memory_size_mb,
            details=details,
        )
        self._add_record(record)
        return record.event_id

    def log_consolidation(
        self,
        records_consolidated: int,
        memory_before_mb: float,
        memory_after_mb: float,
        latency_ms: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a memory consolidation event.

        Returns:
            Event ID of the created record
        """
        record = self._create_record(
            event_type=AuditEventType.MEMORY_CONSOLIDATION,
            operation="consolidation",
            severity=AuditSeverity.INFO,
            resource="neural_memory",
            memory_size_mb=memory_after_mb,
            latency_ms=latency_ms,
            details={
                "records_consolidated": records_consolidated,
                "memory_before_mb": memory_before_mb,
                "memory_after_mb": memory_after_mb,
                **(details or {}),
            },
        )
        self._add_record(record)
        return record.event_id

    def log_size_limit_warning(
        self,
        current_size_mb: float,
        max_size_mb: float,
        utilization_percent: float,
    ) -> str:
        """Log a size limit warning.

        Returns:
            Event ID of the created record
        """
        record = self._create_record(
            event_type=AuditEventType.SIZE_LIMIT_WARNING,
            operation="size_check",
            severity=AuditSeverity.WARNING,
            resource="neural_memory",
            memory_size_mb=current_size_mb,
            details={
                "max_size_mb": max_size_mb,
                "utilization_percent": utilization_percent,
            },
        )
        self._add_record(record)
        return record.event_id

    def log_size_limit_exceeded(
        self,
        current_size_mb: float,
        max_size_mb: float,
        action_taken: str,
    ) -> str:
        """Log a size limit exceeded event.

        Returns:
            Event ID of the created record
        """
        record = self._create_record(
            event_type=AuditEventType.SIZE_LIMIT_EXCEEDED,
            operation="size_exceeded",
            severity=AuditSeverity.CRITICAL,
            resource="neural_memory",
            memory_size_mb=current_size_mb,
            details={
                "max_size_mb": max_size_mb,
                "action_taken": action_taken,
            },
        )
        self._add_record(record)
        return record.event_id

    def log_service_init(
        self,
        config: Dict[str, Any],
        memory_size_mb: float = 0.0,
    ) -> str:
        """Log service initialization.

        Returns:
            Event ID of the created record
        """
        record = self._create_record(
            event_type=AuditEventType.SERVICE_INIT,
            operation="initialize",
            resource="TitanMemoryService",
            memory_size_mb=memory_size_mb,
            details={"config": config},
        )
        self._add_record(record)
        return record.event_id

    def log_service_shutdown(
        self,
        stats: Dict[str, Any],
    ) -> str:
        """Log service shutdown.

        Returns:
            Event ID of the created record
        """
        record = self._create_record(
            event_type=AuditEventType.SERVICE_SHUTDOWN,
            operation="shutdown",
            resource="TitanMemoryService",
            details={"stats": stats},
        )
        self._add_record(record)
        return record.event_id

    def log_checkpoint_save(
        self,
        path: str,
        memory_size_mb: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log checkpoint save.

        Returns:
            Event ID of the created record
        """
        record = self._create_record(
            event_type=AuditEventType.CHECKPOINT_SAVE,
            operation="save_checkpoint",
            resource=path,
            memory_size_mb=memory_size_mb,
            details=details,
        )
        self._add_record(record)
        return record.event_id

    def log_checkpoint_load(
        self,
        path: str,
        memory_size_mb: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log checkpoint load.

        Returns:
            Event ID of the created record
        """
        record = self._create_record(
            event_type=AuditEventType.CHECKPOINT_LOAD,
            operation="load_checkpoint",
            resource=path,
            memory_size_mb=memory_size_mb,
            details=details,
        )
        self._add_record(record)
        return record.event_id

    def log_error(
        self,
        operation: str,
        error_message: str,
        error_type: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log an error event.

        Returns:
            Event ID of the created record
        """
        self._error_count += 1
        record = self._create_record(
            event_type=AuditEventType.ERROR,
            operation=operation,
            severity=AuditSeverity.ERROR,
            resource="neural_memory",
            details={
                "error_message": error_message,
                "error_type": error_type,
                **(details or {}),
            },
        )
        self._add_record(record)
        return record.event_id

    def flush(self) -> int:
        """Flush pending records to storage.

        Returns:
            Number of records successfully stored
        """
        if not self._pending:
            return 0

        stored = self.storage.store_batch(self._pending)
        logger.debug(f"Flushed {stored}/{len(self._pending)} audit records")
        self._pending = []
        return stored

    def get_stats(self) -> Dict[str, Any]:
        """Get audit logger statistics."""
        return {
            "record_count": self._record_count,
            "error_count": self._error_count,
            "pending_count": len(self._pending),
            "environment": self.environment,
            "batch_size": self.batch_size,
            "auto_flush": self.auto_flush,
        }

    def query(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """Query audit records from storage."""
        # Flush pending before query
        self.flush()
        return self.storage.query(
            start_time=start_time,
            end_time=end_time,
            event_type=event_type,
            correlation_id=correlation_id,
            limit=limit,
        )
