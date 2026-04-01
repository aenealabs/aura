"""Tests for ProvenanceAuditLogger."""

from unittest.mock import MagicMock

import pytest

from src.services.context_provenance.audit_logger import (
    ProvenanceAuditLogger,
    configure_audit_logger,
    get_audit_logger,
    reset_audit_logger,
)
from src.services.context_provenance.contracts import ProvenanceAuditEvent


@pytest.fixture
def audit_logger():
    """Create an audit logger for testing."""
    return ProvenanceAuditLogger(environment="test")


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset global logger after each test."""
    yield
    reset_audit_logger()


class TestProvenanceAuditLogger:
    """Tests for ProvenanceAuditLogger."""

    @pytest.mark.asyncio
    async def test_log_basic_event(self, audit_logger):
        """Test logging a basic audit event."""
        audit_id = await audit_logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="chunk-123",
            details={"status": "passed"},
        )

        assert audit_id is not None
        assert len(audit_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_log_with_user_and_session(self, audit_logger):
        """Test logging with user and session IDs."""
        audit_id = await audit_logger.log(
            event_type=ProvenanceAuditEvent.CONTENT_SERVED,
            chunk_id="chunk-456",
            details={"trust_score": 0.85},
            user_id="user@test.com",
            session_id="session-789",
        )

        logs = audit_logger.get_in_memory_logs()
        record = [r for r in logs if r.audit_id == audit_id][0]

        assert record.user_id == "user@test.com"
        assert record.session_id == "session-789"

    @pytest.mark.asyncio
    async def test_log_integrity_verified(self, audit_logger):
        """Test logging integrity verified event."""
        audit_id = await audit_logger.log_integrity_verified(
            chunk_id="chunk-int",
            hash_match=True,
            hmac_valid=True,
            user_id="verifier",
        )

        logs = audit_logger.get_in_memory_logs()
        record = [r for r in logs if r.audit_id == audit_id][0]

        assert record.event_type == ProvenanceAuditEvent.INTEGRITY_VERIFIED
        assert record.details["hash_match"] is True
        assert record.details["hmac_valid"] is True

    @pytest.mark.asyncio
    async def test_log_integrity_failed(self, audit_logger):
        """Test logging integrity failed event."""
        audit_id = await audit_logger.log_integrity_failed(
            chunk_id="chunk-fail",
            reason="Hash mismatch",
            expected_hash="abc123def456789",
            computed_hash="xyz987uvw654321",
        )

        logs = audit_logger.get_in_memory_logs()
        record = [r for r in logs if r.audit_id == audit_id][0]

        assert record.event_type == ProvenanceAuditEvent.INTEGRITY_FAILED
        assert "Hash mismatch" in record.details["reason"]

    @pytest.mark.asyncio
    async def test_log_trust_computed(self, audit_logger):
        """Test logging trust computed event."""
        audit_id = await audit_logger.log_trust_computed(
            chunk_id="chunk-trust",
            trust_score=0.75,
            trust_level="medium",
            components={
                "repository": 0.8,
                "author": 0.7,
                "age": 0.9,
                "verification": 0.6,
            },
        )

        logs = audit_logger.get_in_memory_logs()
        record = [r for r in logs if r.audit_id == audit_id][0]

        assert record.event_type == ProvenanceAuditEvent.TRUST_COMPUTED
        assert record.details["trust_score"] == 0.75
        assert record.details["trust_level"] == "medium"

    @pytest.mark.asyncio
    async def test_log_anomaly_detected(self, audit_logger):
        """Test logging anomaly detected event."""
        audit_id = await audit_logger.log_anomaly_detected(
            chunk_id="chunk-anomaly",
            anomaly_score=0.9,
            anomaly_types=["hidden_instruction", "obfuscated_code"],
            suspicious_spans=[(0, 50, "Hidden pattern")],
        )

        logs = audit_logger.get_in_memory_logs()
        record = [r for r in logs if r.audit_id == audit_id][0]

        assert record.event_type == ProvenanceAuditEvent.ANOMALY_DETECTED
        assert record.details["anomaly_score"] == 0.9
        assert len(record.details["anomaly_types"]) == 2

    @pytest.mark.asyncio
    async def test_log_content_quarantined(self, audit_logger):
        """Test logging content quarantined event."""
        audit_id = await audit_logger.log_content_quarantined(
            chunk_id="chunk-quar",
            reason="integrity_failure",
            details="Content hash mismatch detected",
            repository_id="org/repo",
        )

        logs = audit_logger.get_in_memory_logs()
        record = [r for r in logs if r.audit_id == audit_id][0]

        assert record.event_type == ProvenanceAuditEvent.CONTENT_QUARANTINED
        assert record.details["reason"] == "integrity_failure"
        assert record.details["repository_id"] == "org/repo"

    @pytest.mark.asyncio
    async def test_log_content_served(self, audit_logger):
        """Test logging content served event."""
        audit_id = await audit_logger.log_content_served(
            chunk_id="chunk-serve",
            trust_score=0.85,
            served_to="user@test.com",
            session_id="session-123",
        )

        logs = audit_logger.get_in_memory_logs()
        record = [r for r in logs if r.audit_id == audit_id][0]

        assert record.event_type == ProvenanceAuditEvent.CONTENT_SERVED
        assert record.details["trust_score"] == 0.85
        assert record.session_id == "session-123"

    @pytest.mark.asyncio
    async def test_query_by_chunk(self, audit_logger):
        """Test querying events by chunk ID."""
        chunk_id = "query-chunk"

        # Log multiple events for same chunk
        await audit_logger.log_integrity_verified(chunk_id, True, True)
        await audit_logger.log_trust_computed(chunk_id, 0.8, "high", {})
        await audit_logger.log_content_served(chunk_id, 0.8)

        # Log events for different chunk
        await audit_logger.log_integrity_verified("other-chunk", True, True)

        results = await audit_logger.query_by_chunk(chunk_id)

        assert len(results) == 3
        assert all(r["chunk_id"] == chunk_id for r in results)

    @pytest.mark.asyncio
    async def test_query_by_event_type(self, audit_logger):
        """Test querying events by type."""
        # Log various event types
        await audit_logger.log_integrity_verified("c1", True, True)
        await audit_logger.log_integrity_verified("c2", True, True)
        await audit_logger.log_integrity_failed("c3", "Failed")
        await audit_logger.log_anomaly_detected("c4", 0.9, ["test"])

        results = await audit_logger.query_by_event_type(
            ProvenanceAuditEvent.INTEGRITY_VERIFIED
        )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_recent_failures(self, audit_logger):
        """Test getting recent failures."""
        await audit_logger.log_integrity_failed("c1", "Failed 1")
        await audit_logger.log_anomaly_detected("c2", 0.9, ["anomaly"])
        await audit_logger.log_integrity_verified("c3", True, True)  # Not a failure

        failures = await audit_logger.get_recent_failures()

        assert len(failures) >= 2

    @pytest.mark.asyncio
    async def test_in_memory_logs(self, audit_logger):
        """Test in-memory log storage."""
        await audit_logger.log(
            event_type=ProvenanceAuditEvent.CONTENT_INDEXED,
            chunk_id="memory-test",
            details={"test": True},
        )

        logs = audit_logger.get_in_memory_logs()

        assert len(logs) >= 1
        assert any(r.chunk_id == "memory-test" for r in logs)

    @pytest.mark.asyncio
    async def test_clear_in_memory_logs(self, audit_logger):
        """Test clearing in-memory logs."""
        await audit_logger.log(
            event_type=ProvenanceAuditEvent.CONTENT_INDEXED,
            chunk_id="clear-test",
            details={},
        )

        count = audit_logger.clear_in_memory_logs()

        assert count >= 1
        assert len(audit_logger.get_in_memory_logs()) == 0


class TestAuditLoggerWithMocks:
    """Tests for ProvenanceAuditLogger with mocked clients."""

    @pytest.mark.asyncio
    async def test_log_sends_to_eventbridge_for_failures(self):
        """Test that security-critical events go to EventBridge."""
        mock_eventbridge = MagicMock()

        logger = ProvenanceAuditLogger(
            eventbridge_client=mock_eventbridge,
            event_bus="test-bus",
            environment="test",
        )

        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_FAILED,
            chunk_id="event-test",
            details={"reason": "test"},
        )

        mock_eventbridge.put_events.assert_called_once()
        call_args = mock_eventbridge.put_events.call_args
        entries = call_args.kwargs["Entries"]
        assert len(entries) == 1
        assert entries[0]["EventBusName"] == "test-bus"
        assert entries[0]["Source"] == "aura.context-provenance"

    @pytest.mark.asyncio
    async def test_log_sends_to_eventbridge_for_anomalies(self):
        """Test that anomaly events go to EventBridge."""
        mock_eventbridge = MagicMock()

        logger = ProvenanceAuditLogger(
            eventbridge_client=mock_eventbridge,
            event_bus="test-bus",
            environment="test",
        )

        await logger.log(
            event_type=ProvenanceAuditEvent.ANOMALY_DETECTED,
            chunk_id="anomaly-test",
            details={"score": 0.9},
        )

        mock_eventbridge.put_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_sends_to_eventbridge_for_quarantine(self):
        """Test that quarantine events go to EventBridge."""
        mock_eventbridge = MagicMock()

        logger = ProvenanceAuditLogger(
            eventbridge_client=mock_eventbridge,
            event_bus="test-bus",
            environment="test",
        )

        await logger.log(
            event_type=ProvenanceAuditEvent.CONTENT_QUARANTINED,
            chunk_id="quarantine-test",
            details={"reason": "suspicious"},
        )

        mock_eventbridge.put_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_does_not_send_to_eventbridge_for_normal_events(self):
        """Test that normal events don't go to EventBridge."""
        mock_eventbridge = MagicMock()

        logger = ProvenanceAuditLogger(
            eventbridge_client=mock_eventbridge,
            event_bus="test-bus",
            environment="test",
        )

        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="normal-test",
            details={"status": "ok"},
        )

        mock_eventbridge.put_events.assert_not_called()


class TestAuditLoggerSingleton:
    """Tests for global singleton management."""

    def test_get_audit_logger(self):
        """Test getting global logger instance."""
        logger = get_audit_logger()
        assert logger is not None

    def test_configure_audit_logger(self):
        """Test configuring global logger."""
        logger = configure_audit_logger(
            table_name="custom-audit",
            log_group="/custom/logs",
            environment="custom",
        )

        assert logger is not None
        assert "custom" in logger.table_name

    def test_reset_audit_logger(self):
        """Test resetting global logger."""
        logger1 = get_audit_logger()
        reset_audit_logger()
        logger2 = get_audit_logger()

        assert logger1 is not logger2


class TestAuditEventTypes:
    """Tests for all audit event types."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "event_type",
        [
            ProvenanceAuditEvent.CONTENT_INDEXED,
            ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            ProvenanceAuditEvent.INTEGRITY_FAILED,
            ProvenanceAuditEvent.TRUST_COMPUTED,
            ProvenanceAuditEvent.LOW_TRUST_EXCLUDED,
            ProvenanceAuditEvent.ANOMALY_DETECTED,
            ProvenanceAuditEvent.CONTENT_QUARANTINED,
            ProvenanceAuditEvent.QUARANTINE_REVIEWED,
            ProvenanceAuditEvent.CONTENT_SERVED,
        ],
    )
    async def test_can_log_all_event_types(self, audit_logger, event_type):
        """Test that all event types can be logged."""
        audit_id = await audit_logger.log(
            event_type=event_type,
            chunk_id="test-chunk",
            details={"test": True},
        )

        assert audit_id is not None

        logs = audit_logger.get_in_memory_logs()
        record = [r for r in logs if r.audit_id == audit_id][0]
        assert record.event_type == event_type
