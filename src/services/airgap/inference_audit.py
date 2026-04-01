"""
Inference Audit Logging for Air-Gapped Deployments.

Provides comprehensive audit logging for LLM inference operations
as required for compliance in regulated environments (CMMC, SOX, HIPAA).
"""

import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from queue import Queue
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class InferenceEventType(str, Enum):
    """Types of inference events to audit."""

    INFERENCE_REQUEST = "inference_request"
    INFERENCE_RESPONSE = "inference_response"
    INFERENCE_ERROR = "inference_error"
    MODEL_LOAD = "model_load"
    MODEL_UNLOAD = "model_unload"
    TOKEN_USAGE = "token_usage"
    RATE_LIMIT = "rate_limit"
    ACCESS_DENIED = "access_denied"


@dataclass
class InferenceAuditEvent:
    """Audit event for inference operations."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: InferenceEventType = InferenceEventType.INFERENCE_REQUEST
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Request context
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    session_id: Optional[str] = None
    source_ip: Optional[str] = None

    # Model context
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    inference_endpoint: Optional[str] = None

    # Request details (hashed for privacy)
    prompt_hash: Optional[str] = None
    prompt_length: int = 0
    response_hash: Optional[str] = None
    response_length: int = 0

    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Performance
    latency_ms: float = 0.0
    queue_time_ms: float = 0.0

    # Status
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Additional metadata
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "session_id": self.session_id,
            "source_ip": self.source_ip,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "inference_endpoint": self.inference_endpoint,
            "prompt_hash": self.prompt_hash,
            "prompt_length": self.prompt_length,
            "response_hash": self.response_hash,
            "response_length": self.response_length,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "queue_time_ms": self.queue_time_ms,
            "success": self.success,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class InferenceAuditLogger:
    """
    Audit logger for LLM inference operations.

    Provides:
    - Structured audit logging to files and/or syslog
    - Asynchronous logging with buffering
    - Log rotation and retention
    - Privacy-preserving hashing of prompts/responses
    - SIEM-compatible output format
    """

    def __init__(
        self,
        log_dir: Optional[str] = None,
        log_to_file: bool = True,
        log_to_syslog: bool = False,
        buffer_size: int = 1000,
        flush_interval_seconds: float = 5.0,
        retention_days: int = 365,
        hash_content: bool = True,
    ):
        """
        Initialize audit logger.

        Args:
            log_dir: Directory for audit log files
            log_to_file: Write logs to files
            log_to_syslog: Send logs to syslog
            buffer_size: Maximum events to buffer before flush
            flush_interval_seconds: Interval between automatic flushes
            retention_days: Days to retain audit logs
            hash_content: Hash prompt/response content for privacy
        """
        self._log_dir = Path(
            log_dir or os.getenv("AURA_AUDIT_LOG_DIR", "/var/log/aura/audit")
        )
        self._log_to_file = log_to_file
        self._log_to_syslog = log_to_syslog
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval_seconds
        self._retention_days = retention_days
        self._should_hash_content = hash_content

        self._event_queue: Queue = Queue(maxsize=buffer_size * 2)
        self._shutdown = threading.Event()
        self._flush_thread: Optional[threading.Thread] = None

        # Initialize logging
        self._setup_logging()

        # Start background flush thread
        if self._log_to_file or self._log_to_syslog:
            self._start_flush_thread()

    def _setup_logging(self) -> None:
        """Set up audit log handlers."""
        self._audit_logger = logging.getLogger("aura.audit.inference")
        self._audit_logger.setLevel(logging.INFO)
        self._audit_logger.propagate = False

        # File handler
        if self._log_to_file:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self._log_dir / "inference_audit.jsonl"

            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=100 * 1024 * 1024,  # 100MB
                backupCount=self._retention_days,
            )
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            self._audit_logger.addHandler(file_handler)

        # Syslog handler
        if self._log_to_syslog:
            try:
                syslog_handler = logging.handlers.SysLogHandler(
                    address="/dev/log",
                    facility=logging.handlers.SysLogHandler.LOG_LOCAL0,
                )
                syslog_handler.setFormatter(
                    logging.Formatter("aura-inference-audit: %(message)s")
                )
                self._audit_logger.addHandler(syslog_handler)
            except Exception as e:
                logger.warning("Failed to configure syslog: %s", e)

    def _start_flush_thread(self) -> None:
        """Start background thread for flushing events."""
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="inference-audit-flush",
        )
        self._flush_thread.start()

    def _flush_loop(self) -> None:
        """Background loop for flushing events."""
        while not self._shutdown.is_set():
            try:
                self._flush_events()
            except Exception as e:
                logger.error("Error flushing audit events: %s", e)

            self._shutdown.wait(timeout=self._flush_interval)

    def _flush_events(self) -> None:
        """Flush buffered events to log."""
        events_flushed = 0

        while not self._event_queue.empty():
            try:
                event = self._event_queue.get_nowait()
                self._audit_logger.info(event.to_json())
                events_flushed += 1
            except Exception:
                break

        if events_flushed > 0:
            logger.debug("Flushed %d audit events", events_flushed)

    def _compute_hash(self, content: str) -> str:
        """Hash content for privacy-preserving logging."""
        if not content:
            return ""
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def log_inference_request(
        self,
        request_id: str,
        model_name: str,
        prompt: str,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> InferenceAuditEvent:
        """
        Log an inference request.

        Args:
            request_id: Unique request identifier
            model_name: Name of the model being called
            prompt: User prompt (will be hashed)
            user_id: User making the request
            organization_id: Organization of the user
            source_ip: Source IP address
            metadata: Additional metadata

        Returns:
            InferenceAuditEvent for correlation with response
        """
        event = InferenceAuditEvent(
            event_type=InferenceEventType.INFERENCE_REQUEST,
            request_id=request_id,
            user_id=user_id,
            organization_id=organization_id,
            source_ip=source_ip,
            model_name=model_name,
            prompt_hash=(
                self._compute_hash(prompt) if self._should_hash_content else None
            ),
            prompt_length=len(prompt),
            metadata=metadata or {},
        )

        self._queue_event(event)
        return event

    def log_inference_response(
        self,
        request_id: str,
        model_name: str,
        response: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> InferenceAuditEvent:
        """
        Log an inference response.

        Args:
            request_id: Request ID to correlate with request
            model_name: Name of the model
            response: Model response (will be hashed)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            latency_ms: Request latency in milliseconds
            user_id: User who made the request
            metadata: Additional metadata

        Returns:
            InferenceAuditEvent
        """
        event = InferenceAuditEvent(
            event_type=InferenceEventType.INFERENCE_RESPONSE,
            request_id=request_id,
            user_id=user_id,
            model_name=model_name,
            response_hash=(
                self._compute_hash(response) if self._should_hash_content else None
            ),
            response_length=len(response),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
            success=True,
            metadata=metadata or {},
        )

        self._queue_event(event)
        return event

    def log_inference_error(
        self,
        request_id: str,
        model_name: str,
        error_code: str,
        error_message: str,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> InferenceAuditEvent:
        """
        Log an inference error.

        Args:
            request_id: Request ID
            model_name: Name of the model
            error_code: Error code
            error_message: Error message
            user_id: User who made the request
            metadata: Additional metadata

        Returns:
            InferenceAuditEvent
        """
        event = InferenceAuditEvent(
            event_type=InferenceEventType.INFERENCE_ERROR,
            request_id=request_id,
            user_id=user_id,
            model_name=model_name,
            success=False,
            error_code=error_code,
            error_message=error_message,
            metadata=metadata or {},
        )

        self._queue_event(event)
        return event

    def log_token_usage(
        self,
        user_id: str,
        organization_id: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        period_start: datetime,
        period_end: datetime,
    ) -> InferenceAuditEvent:
        """
        Log aggregated token usage.

        Args:
            user_id: User ID
            organization_id: Organization ID
            model_name: Model name
            input_tokens: Total input tokens in period
            output_tokens: Total output tokens in period
            period_start: Start of usage period
            period_end: End of usage period

        Returns:
            InferenceAuditEvent
        """
        event = InferenceAuditEvent(
            event_type=InferenceEventType.TOKEN_USAGE,
            user_id=user_id,
            organization_id=organization_id,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            metadata={
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
        )

        self._queue_event(event)
        return event

    def log_access_denied(
        self,
        request_id: str,
        user_id: str,
        model_name: str,
        reason: str,
        source_ip: Optional[str] = None,
    ) -> InferenceAuditEvent:
        """
        Log access denied event.

        Args:
            request_id: Request ID
            user_id: User who was denied
            model_name: Model they tried to access
            reason: Reason for denial
            source_ip: Source IP address

        Returns:
            InferenceAuditEvent
        """
        event = InferenceAuditEvent(
            event_type=InferenceEventType.ACCESS_DENIED,
            request_id=request_id,
            user_id=user_id,
            model_name=model_name,
            source_ip=source_ip,
            success=False,
            error_code="ACCESS_DENIED",
            error_message=reason,
        )

        self._queue_event(event)
        return event

    def _queue_event(self, event: InferenceAuditEvent) -> None:
        """Add event to queue for async logging."""
        try:
            self._event_queue.put_nowait(event)
        except Exception:
            # Queue full, log immediately
            logger.warning("Audit queue full, logging synchronously")
            self._audit_logger.info(event.to_json())

    def flush(self) -> None:
        """Flush all buffered events."""
        self._flush_events()

    def shutdown(self) -> None:
        """Shutdown the audit logger."""
        self._shutdown.set()
        self.flush()

        if self._flush_thread:
            self._flush_thread.join(timeout=5.0)


# Import handlers for RotatingFileHandler
import logging.handlers

# Global audit logger instance
_audit_logger: Optional[InferenceAuditLogger] = None


def get_inference_audit_logger() -> InferenceAuditLogger:
    """Get the global inference audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = InferenceAuditLogger()
    return _audit_logger


def set_inference_audit_logger(logger_instance: InferenceAuditLogger) -> None:
    """Set the global inference audit logger (for testing)."""
    global _audit_logger
    _audit_logger = logger_instance
