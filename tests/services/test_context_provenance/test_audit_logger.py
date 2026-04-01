"""
Tests for provenance audit logger.

Tests audit event logging, multi-destination writes, and queries.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.context_provenance import (
    AuditRecord,
    ProvenanceAuditEvent,
    ProvenanceAuditLogger,
    configure_audit_logger,
    get_audit_logger,
    reset_audit_logger,
)


class TestProvenanceAuditLogger:
    """Test ProvenanceAuditLogger class."""

    def test_initialization(self):
        """Test logger initialization."""
        logger = ProvenanceAuditLogger()
        assert logger.dynamodb is None
        assert logger.eventbridge is None
        assert logger.logs is None
        assert logger.environment == "dev"

    def test_initialization_with_clients(self):
        """Test logger initialization with clients."""
        dynamodb = MagicMock()
        eventbridge = MagicMock()
        logs = MagicMock()

        logger = ProvenanceAuditLogger(
            dynamodb_client=dynamodb,
            eventbridge_client=eventbridge,
            cloudwatch_logs_client=logs,
            environment="qa",
        )

        assert logger.dynamodb is dynamodb
        assert logger.eventbridge is eventbridge
        assert logger.logs is logs
        assert logger.table_name == "aura-provenance-audit-qa"
        assert logger.log_group == "/aura/provenance/audit/qa"

    def test_initialization_custom_names(self):
        """Test logger initialization with custom names."""
        logger = ProvenanceAuditLogger(
            table_name="custom-audit-table",
            log_group="/custom/log/group",
            event_bus="custom-events",
            environment="prod",
        )

        assert logger.table_name == "custom-audit-table-prod"
        assert logger.log_group == "/custom/log/group/prod"
        assert logger.event_bus == "custom-events"


class TestLog:
    """Test log method."""

    @pytest.fixture
    def logger(self):
        """Create logger for tests."""
        return ProvenanceAuditLogger(environment="test")

    @pytest.mark.asyncio
    async def test_log_basic(self, logger: ProvenanceAuditLogger):
        """Test basic audit logging."""
        audit_id = await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="chunk-001",
            details={"hash_match": True, "hmac_valid": True},
        )

        assert audit_id is not None
        assert len(logger._in_memory_log) == 1

        record = logger._in_memory_log[0]
        assert record.event_type == ProvenanceAuditEvent.INTEGRITY_VERIFIED
        assert record.chunk_id == "chunk-001"
        assert record.details["hash_match"] is True

    @pytest.mark.asyncio
    async def test_log_with_user_and_session(self, logger: ProvenanceAuditLogger):
        """Test logging with user and session IDs."""
        await logger.log(
            event_type=ProvenanceAuditEvent.CONTENT_SERVED,
            chunk_id="chunk-001",
            details={"trust_score": 0.85},
            user_id="user-001",
            session_id="session-abc",
        )

        record = logger._in_memory_log[0]
        assert record.user_id == "user-001"
        assert record.session_id == "session-abc"

    @pytest.mark.asyncio
    async def test_log_returns_unique_ids(self, logger: ProvenanceAuditLogger):
        """Test that each log call returns unique ID."""
        ids = []
        for i in range(5):
            audit_id = await logger.log(
                event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
                chunk_id=f"chunk-{i}",
                details={},
            )
            ids.append(audit_id)

        assert len(ids) == 5
        assert len(set(ids)) == 5  # All unique


class TestLogHelperMethods:
    """Test convenience logging methods."""

    @pytest.fixture
    def logger(self):
        """Create logger for tests."""
        return ProvenanceAuditLogger(environment="test")

    @pytest.mark.asyncio
    async def test_log_integrity_verified(self, logger: ProvenanceAuditLogger):
        """Test log_integrity_verified helper."""
        await logger.log_integrity_verified(
            chunk_id="chunk-001",
            hash_match=True,
            hmac_valid=True,
            user_id="user-001",
        )

        record = logger._in_memory_log[0]
        assert record.event_type == ProvenanceAuditEvent.INTEGRITY_VERIFIED
        assert record.details["hash_match"] is True
        assert record.details["hmac_valid"] is True

    @pytest.mark.asyncio
    async def test_log_integrity_failed(self, logger: ProvenanceAuditLogger):
        """Test log_integrity_failed helper."""
        await logger.log_integrity_failed(
            chunk_id="chunk-001",
            reason="Hash mismatch",
            expected_hash="abc123def456789",
            computed_hash="xyz987654321abc",
        )

        record = logger._in_memory_log[0]
        assert record.event_type == ProvenanceAuditEvent.INTEGRITY_FAILED
        assert record.details["reason"] == "Hash mismatch"
        assert "abc123def456789"[:16] in record.details["expected_hash"]

    @pytest.mark.asyncio
    async def test_log_trust_computed(self, logger: ProvenanceAuditLogger):
        """Test log_trust_computed helper."""
        await logger.log_trust_computed(
            chunk_id="chunk-001",
            trust_score=0.85,
            trust_level="HIGH",
            components={"repository": 1.0, "author": 0.8},
        )

        record = logger._in_memory_log[0]
        assert record.event_type == ProvenanceAuditEvent.TRUST_COMPUTED
        assert record.details["trust_score"] == 0.85
        assert record.details["trust_level"] == "HIGH"

    @pytest.mark.asyncio
    async def test_log_anomaly_detected(self, logger: ProvenanceAuditLogger):
        """Test log_anomaly_detected helper."""
        await logger.log_anomaly_detected(
            chunk_id="chunk-001",
            anomaly_score=0.9,
            anomaly_types=["INJECTION_PATTERN", "HIDDEN_INSTRUCTION"],
            suspicious_spans=[(100, 150, "injection"), (200, 250, "hidden")],
        )

        record = logger._in_memory_log[0]
        assert record.event_type == ProvenanceAuditEvent.ANOMALY_DETECTED
        assert record.details["anomaly_score"] == 0.9
        assert len(record.details["anomaly_types"]) == 2
        assert record.details["suspicious_spans_count"] == 2

    @pytest.mark.asyncio
    async def test_log_content_quarantined(self, logger: ProvenanceAuditLogger):
        """Test log_content_quarantined helper."""
        await logger.log_content_quarantined(
            chunk_id="chunk-001",
            reason="INTEGRITY_FAILURE",
            details="Hash mismatch detected",
            repository_id="org/repo",
        )

        record = logger._in_memory_log[0]
        assert record.event_type == ProvenanceAuditEvent.CONTENT_QUARANTINED
        assert record.details["reason"] == "INTEGRITY_FAILURE"
        assert record.details["repository_id"] == "org/repo"

    @pytest.mark.asyncio
    async def test_log_content_served(self, logger: ProvenanceAuditLogger):
        """Test log_content_served helper."""
        await logger.log_content_served(
            chunk_id="chunk-001",
            trust_score=0.92,
            served_to="user-001",
            session_id="session-abc",
        )

        record = logger._in_memory_log[0]
        assert record.event_type == ProvenanceAuditEvent.CONTENT_SERVED
        assert record.details["trust_score"] == 0.92
        assert record.details["served_to"] == "user-001"


class TestDynamoDBWriting:
    """Test DynamoDB writing."""

    @pytest.fixture
    def dynamodb_mock(self):
        """Create mock DynamoDB client."""
        mock = MagicMock()
        mock.put_item.return_value = {}
        mock.query.return_value = {"Items": []}
        return mock

    @pytest.fixture
    def logger(self, dynamodb_mock):
        """Create logger with mock DynamoDB."""
        return ProvenanceAuditLogger(
            dynamodb_client=dynamodb_mock,
            environment="test",
        )

    @pytest.mark.asyncio
    async def test_writes_to_dynamodb(
        self,
        logger: ProvenanceAuditLogger,
        dynamodb_mock,
    ):
        """Test that logs are written to DynamoDB."""
        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="chunk-001",
            details={"hash_match": True},
        )

        dynamodb_mock.put_item.assert_called_once()
        call_kwargs = dynamodb_mock.put_item.call_args[1]
        assert call_kwargs["TableName"] == "aura-provenance-audit-test"


class TestCloudWatchWriting:
    """Test CloudWatch Logs writing."""

    @pytest.fixture
    def logs_mock(self):
        """Create mock CloudWatch Logs client."""
        mock = MagicMock()
        mock.create_log_stream.return_value = {}
        mock.put_log_events.return_value = {}
        return mock

    @pytest.fixture
    def logger(self, logs_mock):
        """Create logger with mock CloudWatch Logs."""
        return ProvenanceAuditLogger(
            cloudwatch_logs_client=logs_mock,
            environment="test",
        )

    @pytest.mark.asyncio
    async def test_writes_to_cloudwatch(
        self,
        logger: ProvenanceAuditLogger,
        logs_mock,
    ):
        """Test that logs are written to CloudWatch."""
        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="chunk-001",
            details={"hash_match": True},
        )

        # Should create log stream and write
        assert logs_mock.create_log_stream.called or logs_mock.put_log_events.called


class TestEventBridgeSending:
    """Test EventBridge event sending."""

    @pytest.fixture
    def eventbridge_mock(self):
        """Create mock EventBridge client."""
        mock = MagicMock()
        mock.put_events.return_value = {"FailedEntryCount": 0}
        return mock

    @pytest.fixture
    def logger(self, eventbridge_mock):
        """Create logger with mock EventBridge."""
        return ProvenanceAuditLogger(
            eventbridge_client=eventbridge_mock,
            environment="test",
        )

    @pytest.mark.asyncio
    async def test_sends_security_events_to_eventbridge(
        self,
        logger: ProvenanceAuditLogger,
        eventbridge_mock,
    ):
        """Test that security events go to EventBridge."""
        # INTEGRITY_FAILED should trigger EventBridge
        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_FAILED,
            chunk_id="chunk-001",
            details={"reason": "Hash mismatch"},
        )

        eventbridge_mock.put_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_anomaly_detected_to_eventbridge(
        self,
        logger: ProvenanceAuditLogger,
        eventbridge_mock,
    ):
        """Test that anomaly events go to EventBridge."""
        await logger.log(
            event_type=ProvenanceAuditEvent.ANOMALY_DETECTED,
            chunk_id="chunk-001",
            details={"anomaly_score": 0.9},
        )

        eventbridge_mock.put_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_content_quarantined_to_eventbridge(
        self,
        logger: ProvenanceAuditLogger,
        eventbridge_mock,
    ):
        """Test that quarantine events go to EventBridge."""
        await logger.log(
            event_type=ProvenanceAuditEvent.CONTENT_QUARANTINED,
            chunk_id="chunk-001",
            details={"reason": "Anomaly detected"},
        )

        eventbridge_mock.put_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_security_events_skip_eventbridge(
        self,
        logger: ProvenanceAuditLogger,
        eventbridge_mock,
    ):
        """Test that non-security events don't go to EventBridge."""
        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="chunk-001",
            details={"hash_match": True},
        )

        eventbridge_mock.put_events.assert_not_called()


class TestQueryByChunk:
    """Test query_by_chunk method."""

    @pytest.fixture
    def logger(self):
        """Create logger for tests."""
        return ProvenanceAuditLogger(environment="test")

    @pytest.mark.asyncio
    async def test_query_by_chunk_basic(self, logger: ProvenanceAuditLogger):
        """Test querying by chunk ID."""
        # Add some records
        for i in range(3):
            await logger.log(
                event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
                chunk_id="target-chunk",
                details={"index": i},
            )

        # Add record for different chunk
        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="other-chunk",
            details={"index": 99},
        )

        results = await logger.query_by_chunk("target-chunk")
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_query_by_chunk_with_time_range(self, logger: ProvenanceAuditLogger):
        """Test querying with time range."""
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=1)
        end_time = now + timedelta(hours=1)

        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="chunk-001",
            details={},
        )

        results = await logger.query_by_chunk(
            "chunk-001",
            start_time=start_time,
            end_time=end_time,
        )
        assert len(results) == 1


class TestQueryByEventType:
    """Test query_by_event_type method."""

    @pytest.fixture
    def logger(self):
        """Create logger for tests."""
        return ProvenanceAuditLogger(environment="test")

    @pytest.mark.asyncio
    async def test_query_by_event_type(self, logger: ProvenanceAuditLogger):
        """Test querying by event type."""
        # Add different event types
        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="chunk-001",
            details={},
        )
        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_FAILED,
            chunk_id="chunk-002",
            details={},
        )
        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="chunk-003",
            details={},
        )

        results = await logger.query_by_event_type(
            ProvenanceAuditEvent.INTEGRITY_VERIFIED
        )
        assert len(results) == 2


class TestGetRecentFailures:
    """Test get_recent_failures method."""

    @pytest.fixture
    def logger(self):
        """Create logger for tests."""
        return ProvenanceAuditLogger(environment="test")

    @pytest.mark.asyncio
    async def test_get_recent_failures(self, logger: ProvenanceAuditLogger):
        """Test getting recent failures."""
        # Add various events
        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="chunk-001",
            details={},
        )
        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_FAILED,
            chunk_id="chunk-002",
            details={},
        )
        await logger.log(
            event_type=ProvenanceAuditEvent.ANOMALY_DETECTED,
            chunk_id="chunk-003",
            details={},
        )

        failures = await logger.get_recent_failures()
        assert len(failures) == 2


class TestInMemoryLogs:
    """Test in-memory log management."""

    @pytest.fixture
    def logger(self):
        """Create logger for tests."""
        return ProvenanceAuditLogger(environment="test")

    def test_get_in_memory_logs(self, logger: ProvenanceAuditLogger):
        """Test getting in-memory logs."""
        logs = logger.get_in_memory_logs()
        assert logs == []

    @pytest.mark.asyncio
    async def test_get_in_memory_logs_after_logging(
        self,
        logger: ProvenanceAuditLogger,
    ):
        """Test getting logs after adding records."""
        await logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="chunk-001",
            details={},
        )

        logs = logger.get_in_memory_logs()
        assert len(logs) == 1

    def test_clear_in_memory_logs(self, logger: ProvenanceAuditLogger):
        """Test clearing in-memory logs."""
        # Add some records directly
        logger._in_memory_log.append(
            AuditRecord(
                audit_id="audit-001",
                event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
                chunk_id="chunk-001",
                timestamp=datetime.now(timezone.utc),
                details={},
            )
        )

        cleared = logger.clear_in_memory_logs()
        assert cleared == 1
        assert len(logger._in_memory_log) == 0


class TestLogStreamName:
    """Test log stream name generation."""

    def test_get_log_stream_name(self):
        """Test log stream name format."""
        logger = ProvenanceAuditLogger()
        stream_name = logger._get_log_stream_name()

        assert stream_name.startswith("provenance-")
        assert datetime.now(timezone.utc).strftime("%Y-%m-%d") in stream_name


class TestSingletonFunctions:
    """Test singleton management functions."""

    def test_get_audit_logger(self):
        """Test get_audit_logger returns singleton."""
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2

    def test_reset_audit_logger(self):
        """Test reset_audit_logger creates new instance."""
        logger1 = get_audit_logger()
        reset_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is not logger2

    def test_configure_audit_logger(self):
        """Test configure_audit_logger."""
        dynamodb = MagicMock()
        eventbridge = MagicMock()
        logs = MagicMock()

        logger = configure_audit_logger(
            dynamodb_client=dynamodb,
            eventbridge_client=eventbridge,
            cloudwatch_logs_client=logs,
            table_name="custom-audit",
            log_group="/custom/logs",
            event_bus="custom-bus",
            environment="prod",
        )

        assert logger.dynamodb is dynamodb
        assert logger.eventbridge is eventbridge
        assert logger.logs is logs
        assert logger.table_name == "custom-audit-prod"
        assert logger.log_group == "/custom/logs/prod"
        assert logger.event_bus == "custom-bus"
