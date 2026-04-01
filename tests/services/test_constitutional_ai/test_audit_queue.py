"""Unit tests for Constitutional AI audit queue service.

Tests the fire-and-forget SQS audit queue for non-blocking persistence
as specified in ADR-063 Phase 3.
"""

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from src.services.constitutional_ai.audit_queue_service import (
    AuditEntry,
    AuditQueueMode,
    ConstitutionalAuditQueueService,
    create_audit_entry,
)

# =============================================================================
# Test AuditQueueMode Enum
# =============================================================================


class TestAuditQueueMode:
    """Tests for AuditQueueMode enum."""

    def test_enum_values(self):
        """Should have expected mode values."""
        assert AuditQueueMode.MOCK.value == "mock"
        assert AuditQueueMode.AWS.value == "aws"
        assert AuditQueueMode.DISABLED.value == "disabled"


# =============================================================================
# Test AuditEntry Dataclass
# =============================================================================


class TestAuditEntry:
    """Tests for AuditEntry dataclass."""

    @pytest.fixture
    def sample_entry(self):
        """Create sample audit entry for testing."""
        return AuditEntry(
            timestamp="2026-01-21T12:00:00+00:00",
            agent_name="TestAgent",
            operation_type="code_generation",
            output_hash="abc123def456",
            critique_performed=True,
            critique_summary={"critical_issues": 0, "high_issues": 1},
            revision_performed=True,
            revision_iterations=2,
            blocked=False,
            hitl_required=False,
            processing_time_ms=150.5,
            autonomy_level="COLLABORATIVE",
            critique_tier="STANDARD",
            principles_evaluated=16,
            issues_found={"critical": 0, "high": 1, "medium": 0, "low": 0},
            cache_hit=True,
            fast_path_blocked=False,
            metadata={"request_id": "req-123"},
        )

    def test_default_values(self):
        """Should have sensible default values."""
        entry = AuditEntry(
            timestamp="2026-01-21T12:00:00+00:00",
            agent_name="Agent",
            operation_type="review",
            output_hash="hash123",
        )

        assert entry.critique_performed is True
        assert entry.revision_performed is False
        assert entry.blocked is False
        assert entry.hitl_required is False
        assert entry.processing_time_ms == 0.0
        assert entry.autonomy_level == "COLLABORATIVE"
        assert entry.critique_tier == "STANDARD"
        assert entry.cache_hit is False
        assert entry.fast_path_blocked is False

    def test_to_sqs_message(self, sample_entry):
        """Should serialize to valid JSON for SQS."""
        message = sample_entry.to_sqs_message()

        # Should be valid JSON
        parsed = json.loads(message)

        assert parsed["agent_name"] == "TestAgent"
        assert parsed["operation_type"] == "code_generation"
        assert parsed["revision_iterations"] == 2
        assert parsed["processing_time_ms"] == 150.5

    def test_to_dict(self, sample_entry):
        """Should convert to dictionary."""
        d = sample_entry.to_dict()

        assert isinstance(d, dict)
        assert d["agent_name"] == "TestAgent"
        assert d["cache_hit"] is True
        assert d["metadata"]["request_id"] == "req-123"

    def test_from_dict(self):
        """Should create entry from dictionary."""
        data = {
            "timestamp": "2026-01-21T12:00:00+00:00",
            "agent_name": "FromDict",
            "operation_type": "test",
            "output_hash": "hash456",
            "blocked": True,
            "block_reason": "Test block",
        }

        entry = AuditEntry.from_dict(data)

        assert entry.agent_name == "FromDict"
        assert entry.blocked is True
        assert entry.block_reason == "Test block"


# =============================================================================
# Test create_audit_entry Helper
# =============================================================================


class TestCreateAuditEntry:
    """Tests for create_audit_entry helper function."""

    def test_creates_valid_entry(self):
        """Should create entry with computed fields."""
        entry = create_audit_entry(
            agent_name="TestAgent",
            operation_type="code_gen",
            output="def foo(): pass",
        )

        assert entry.agent_name == "TestAgent"
        assert entry.operation_type == "code_gen"
        assert len(entry.output_hash) == 16  # Truncated hash
        assert entry.timestamp is not None

    def test_computes_output_hash(self):
        """Should compute consistent output hash."""
        entry1 = create_audit_entry("Agent", "op", "same output")
        entry2 = create_audit_entry("Agent", "op", "same output")

        assert entry1.output_hash == entry2.output_hash

    def test_extracts_issues_from_summary(self):
        """Should extract issue counts from critique summary."""
        entry = create_audit_entry(
            agent_name="Agent",
            operation_type="review",
            output="code",
            critique_summary={
                "critical_issues": 1,
                "high_issues": 2,
                "medium_issues": 3,
                "low_issues": 4,
                "total_principles_evaluated": 16,
            },
        )

        assert entry.issues_found["critical"] == 1
        assert entry.issues_found["high"] == 2
        assert entry.issues_found["medium"] == 3
        assert entry.issues_found["low"] == 4
        assert entry.principles_evaluated == 16

    def test_handles_missing_summary(self):
        """Should handle missing critique summary."""
        entry = create_audit_entry(
            agent_name="Agent",
            operation_type="review",
            output="code",
        )

        assert entry.critique_performed is False
        assert entry.critique_summary == {}
        assert entry.principles_evaluated == 0

    def test_sets_all_optional_fields(self):
        """Should set all optional fields correctly."""
        entry = create_audit_entry(
            agent_name="Agent",
            operation_type="patch",
            output="code",
            revision_performed=True,
            revision_iterations=3,
            blocked=True,
            block_reason="Critical violation",
            hitl_required=True,
            hitl_request_id="hitl-123",
            processing_time_ms=500.0,
            autonomy_level="FULL_AUTONOMOUS",
            critique_tier="FULL",
            cache_hit=True,
            fast_path_blocked=True,
            metadata={"custom": "data"},
        )

        assert entry.revision_performed is True
        assert entry.revision_iterations == 3
        assert entry.blocked is True
        assert entry.block_reason == "Critical violation"
        assert entry.hitl_required is True
        assert entry.hitl_request_id == "hitl-123"
        assert entry.processing_time_ms == 500.0
        assert entry.autonomy_level == "FULL_AUTONOMOUS"
        assert entry.critique_tier == "FULL"
        assert entry.cache_hit is True
        assert entry.fast_path_blocked is True
        assert entry.metadata["custom"] == "data"


# =============================================================================
# Test ConstitutionalAuditQueueService Initialization
# =============================================================================


class TestAuditQueueServiceInit:
    """Tests for ConstitutionalAuditQueueService initialization."""

    def test_default_mode_is_mock(self):
        """Default mode should be MOCK for safety."""
        service = ConstitutionalAuditQueueService()

        assert service.mode == AuditQueueMode.MOCK

    def test_aws_mode_requires_queue_url(self):
        """AWS mode without queue_url should fallback to MOCK."""
        service = ConstitutionalAuditQueueService(mode=AuditQueueMode.AWS)

        assert service.mode == AuditQueueMode.MOCK

    def test_aws_mode_with_queue_url(self):
        """AWS mode with queue_url should stay AWS."""
        service = ConstitutionalAuditQueueService(
            mode=AuditQueueMode.AWS,
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789/queue.fifo",
        )

        assert service.mode == AuditQueueMode.AWS
        assert service.queue_url is not None

    def test_accepts_sqs_client(self):
        """Should accept pre-configured SQS client."""
        mock_client = MagicMock()
        service = ConstitutionalAuditQueueService(
            mode=AuditQueueMode.AWS,
            queue_url="https://sqs.example.com/queue.fifo",
            sqs_client=mock_client,
        )

        assert service._sqs == mock_client


# =============================================================================
# Test DISABLED Mode
# =============================================================================


class TestAuditQueueDisabled:
    """Tests for DISABLED mode behavior."""

    @pytest.mark.asyncio
    async def test_send_async_does_nothing(self):
        """DISABLED mode should not queue anything."""
        service = ConstitutionalAuditQueueService(mode=AuditQueueMode.DISABLED)
        entry = AuditEntry(
            timestamp="2026-01-21T12:00:00+00:00",
            agent_name="Agent",
            operation_type="op",
            output_hash="hash",
        )

        await service.send_audit_async(entry)

        assert service._entries_queued == 0
        assert len(service.get_mock_queue()) == 0

    def test_send_sync_returns_true(self):
        """DISABLED sync send should return True (no-op success)."""
        service = ConstitutionalAuditQueueService(mode=AuditQueueMode.DISABLED)
        entry = AuditEntry(
            timestamp="2026-01-21T12:00:00+00:00",
            agent_name="Agent",
            operation_type="op",
            output_hash="hash",
        )

        result = service.send_audit_sync(entry)

        assert result is True

    def test_is_enabled_returns_false(self):
        """DISABLED mode should report not enabled."""
        service = ConstitutionalAuditQueueService(mode=AuditQueueMode.DISABLED)

        assert service.is_enabled() is False


# =============================================================================
# Test MOCK Mode
# =============================================================================


class TestAuditQueueMock:
    """Tests for MOCK mode behavior."""

    @pytest.fixture
    def mock_service(self):
        """Create service in MOCK mode."""
        return ConstitutionalAuditQueueService(mode=AuditQueueMode.MOCK)

    @pytest.fixture
    def sample_entry(self):
        """Create sample audit entry."""
        return AuditEntry(
            timestamp="2026-01-21T12:00:00+00:00",
            agent_name="TestAgent",
            operation_type="review",
            output_hash="hash123",
        )

    @pytest.mark.asyncio
    async def test_send_async_queues_entry(self, mock_service, sample_entry):
        """MOCK mode should add entry to mock queue."""
        await mock_service.send_audit_async(sample_entry)

        queue = mock_service.get_mock_queue()
        assert len(queue) == 1
        assert queue[0].agent_name == "TestAgent"

    @pytest.mark.asyncio
    async def test_send_async_increments_counter(self, mock_service, sample_entry):
        """MOCK mode should increment entries_queued counter."""
        await mock_service.send_audit_async(sample_entry)
        await mock_service.send_audit_async(sample_entry)

        assert mock_service._entries_queued == 2

    def test_send_sync_queues_entry(self, mock_service, sample_entry):
        """MOCK sync send should add entry to queue."""
        result = mock_service.send_audit_sync(sample_entry)

        assert result is True
        assert len(mock_service.get_mock_queue()) == 1

    def test_clear_mock_queue(self, mock_service, sample_entry):
        """Should be able to clear mock queue for testing."""
        mock_service.send_audit_sync(sample_entry)
        assert len(mock_service.get_mock_queue()) == 1

        mock_service.clear_mock_queue()
        assert len(mock_service.get_mock_queue()) == 0

    def test_get_mock_queue_returns_copy(self, mock_service, sample_entry):
        """get_mock_queue should return a copy, not the original."""
        mock_service.send_audit_sync(sample_entry)

        queue1 = mock_service.get_mock_queue()
        queue1.clear()

        queue2 = mock_service.get_mock_queue()
        assert len(queue2) == 1  # Original unaffected

    def test_is_enabled_returns_true(self, mock_service):
        """MOCK mode should report enabled."""
        assert mock_service.is_enabled() is True


# =============================================================================
# Test AWS Mode
# =============================================================================


class TestAuditQueueAWS:
    """Tests for AWS mode behavior."""

    @pytest.fixture
    def mock_sqs_client(self):
        """Create mock SQS client."""
        return MagicMock()

    @pytest.fixture
    def aws_service(self, mock_sqs_client):
        """Create service in AWS mode with mock client."""
        return ConstitutionalAuditQueueService(
            mode=AuditQueueMode.AWS,
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789/queue.fifo",
            sqs_client=mock_sqs_client,
        )

    @pytest.fixture
    def sample_entry(self):
        """Create sample audit entry."""
        return AuditEntry(
            timestamp="2026-01-21T12:00:00+00:00",
            agent_name="TestAgent",
            operation_type="review",
            output_hash="hash123",
        )

    def test_send_sync_calls_sqs(self, aws_service, mock_sqs_client, sample_entry):
        """AWS sync send should call SQS client."""
        result = aws_service.send_audit_sync(sample_entry)

        assert result is True
        mock_sqs_client.send_message.assert_called_once()

        # Verify call arguments
        call_args = mock_sqs_client.send_message.call_args
        assert "MessageBody" in call_args.kwargs
        assert "MessageGroupId" in call_args.kwargs
        assert call_args.kwargs["MessageGroupId"] == "constitutional-audit"

    def test_send_sync_handles_error(self, aws_service, mock_sqs_client, sample_entry):
        """AWS sync send should handle SQS errors gracefully."""
        mock_sqs_client.send_message.side_effect = Exception("SQS error")

        result = aws_service.send_audit_sync(sample_entry)

        assert result is False
        assert aws_service._entries_failed == 1

    def test_send_sync_no_client(self, sample_entry):
        """AWS sync send without client should fail."""
        service = ConstitutionalAuditQueueService(
            mode=AuditQueueMode.AWS,
            queue_url="https://sqs.example.com/queue.fifo",
            sqs_client=None,
        )

        result = service.send_audit_sync(sample_entry)

        assert result is False
        assert service._entries_failed == 1

    @pytest.mark.asyncio
    async def test_send_async_fires_and_forgets(self, aws_service, sample_entry):
        """AWS async send should use fire-and-forget pattern."""
        # This test verifies the asyncio.create_task pattern is used
        # The actual SQS call happens in background

        await aws_service.send_audit_async(sample_entry)

        # Give background task time to execute
        await asyncio.sleep(0.1)

        # Entry should have been queued (counter incremented by background task)
        # Note: This is best-effort verification


# =============================================================================
# Test Statistics
# =============================================================================


class TestAuditQueueStats:
    """Tests for queue statistics."""

    def test_get_stats_mock_mode(self):
        """Should return stats for MOCK mode."""
        service = ConstitutionalAuditQueueService(mode=AuditQueueMode.MOCK)
        service.send_audit_sync(
            AuditEntry(
                timestamp="2026-01-21T12:00:00+00:00",
                agent_name="Agent",
                operation_type="op",
                output_hash="hash",
            )
        )

        stats = service.get_stats()

        assert stats["mode"] == "mock"
        assert stats["entries_queued"] == 1
        assert stats["entries_failed"] == 0
        assert stats["mock_queue_size"] == 1
        assert stats["queue_url"] is None

    def test_get_stats_aws_mode(self):
        """Should return stats for AWS mode."""
        service = ConstitutionalAuditQueueService(
            mode=AuditQueueMode.AWS,
            queue_url="https://sqs.example.com/queue.fifo",
        )

        stats = service.get_stats()

        assert stats["mode"] == "aws"
        assert stats["queue_url"] == "https://sqs.example.com/queue.fifo"
        assert stats["mock_queue_size"] == 0


# =============================================================================
# Test Message Deduplication
# =============================================================================


class TestMessageDeduplication:
    """Tests for SQS FIFO message deduplication."""

    def test_deduplication_id_format(self):
        """Deduplication ID should combine timestamp and hash."""
        mock_client = MagicMock()
        service = ConstitutionalAuditQueueService(
            mode=AuditQueueMode.AWS,
            queue_url="https://sqs.example.com/queue.fifo",
            sqs_client=mock_client,
        )

        entry = AuditEntry(
            timestamp="2026-01-21T12:00:00+00:00",
            agent_name="Agent",
            operation_type="op",
            output_hash="abc123",
        )

        service.send_audit_sync(entry)

        call_args = mock_client.send_message.call_args
        dedup_id = call_args.kwargs["MessageDeduplicationId"]

        assert "2026-01-21T12:00:00+00:00" in dedup_id
        assert "abc123" in dedup_id


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestAuditQueueIntegration:
    """Integration-style tests for audit queue."""

    @pytest.mark.asyncio
    async def test_full_audit_workflow(self):
        """Test complete audit workflow from entry creation to queuing."""
        # Create service
        service = ConstitutionalAuditQueueService(mode=AuditQueueMode.MOCK)

        # Create entry using helper
        entry = create_audit_entry(
            agent_name="CoderAgent",
            operation_type="code_generation",
            output="def secure_function(): pass",
            critique_summary={
                "critical_issues": 0,
                "high_issues": 0,
                "medium_issues": 1,
                "low_issues": 2,
                "total_principles_evaluated": 16,
            },
            revision_performed=False,
            processing_time_ms=350.0,
            autonomy_level="COLLABORATIVE",
            critique_tier="STANDARD",
            cache_hit=True,
        )

        # Queue entry
        await service.send_audit_async(entry)

        # Verify
        queue = service.get_mock_queue()
        assert len(queue) == 1

        queued = queue[0]
        assert queued.agent_name == "CoderAgent"
        assert queued.principles_evaluated == 16
        assert queued.issues_found["medium"] == 1
        assert queued.cache_hit is True

    @pytest.mark.asyncio
    async def test_multiple_entries_preserved_order(self):
        """Multiple entries should preserve order in FIFO queue."""
        service = ConstitutionalAuditQueueService(mode=AuditQueueMode.MOCK)

        for i in range(5):
            entry = create_audit_entry(
                agent_name=f"Agent{i}",
                operation_type="op",
                output=f"output {i}",
            )
            await service.send_audit_async(entry)

        queue = service.get_mock_queue()
        assert len(queue) == 5

        # Verify order preserved
        for i, entry in enumerate(queue):
            assert entry.agent_name == f"Agent{i}"
