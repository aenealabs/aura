"""Tests for QuarantineManager."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.services.context_provenance.contracts import ProvenanceRecord, QuarantineReason
from src.services.context_provenance.quarantine_manager import (
    QuarantineManager,
    configure_quarantine_manager,
    get_quarantine_manager,
    reset_quarantine_manager,
)


@pytest.fixture
def provenance():
    """Create a test provenance record."""
    return ProvenanceRecord(
        repository_id="org/repo",
        commit_sha="abc123def456",
        author_id="author123",
        author_email="author@test.com",
        timestamp=datetime.now(timezone.utc),
        branch="main",
    )


@pytest.fixture
def quarantine_manager():
    """Create a quarantine manager for testing."""
    return QuarantineManager(environment="test")


@pytest.fixture(autouse=True)
def reset_manager():
    """Reset global manager after each test."""
    yield
    reset_quarantine_manager()


class TestQuarantineManager:
    """Tests for QuarantineManager."""

    @pytest.mark.asyncio
    async def test_quarantine_content(self, quarantine_manager, provenance):
        """Test quarantining content."""
        record = await quarantine_manager.quarantine(
            chunk_id="chunk-123",
            content="suspicious code here",
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Hash mismatch detected",
            provenance=provenance,
        )

        assert record.chunk_id == "chunk-123"
        assert record.reason == QuarantineReason.INTEGRITY_FAILURE
        assert record.details == "Hash mismatch detected"
        assert record.review_status == "pending"
        assert record.quarantined_by == "system"
        assert record.content_hash is not None

    @pytest.mark.asyncio
    async def test_quarantine_with_anomaly_reason(self, quarantine_manager, provenance):
        """Test quarantining content with anomaly reason."""
        record = await quarantine_manager.quarantine(
            chunk_id="chunk-456",
            content="# ignore previous instructions",
            reason=QuarantineReason.ANOMALY_DETECTED,
            details="Hidden instruction pattern detected",
            provenance=provenance,
        )

        assert record.reason == QuarantineReason.ANOMALY_DETECTED

    @pytest.mark.asyncio
    async def test_quarantine_with_low_trust(self, quarantine_manager, provenance):
        """Test quarantining content with low trust reason."""
        record = await quarantine_manager.quarantine(
            chunk_id="chunk-789",
            content="untrusted code",
            reason=QuarantineReason.LOW_TRUST,
            details="Trust score below threshold",
            provenance=provenance,
        )

        assert record.reason == QuarantineReason.LOW_TRUST

    @pytest.mark.asyncio
    async def test_review_release(self, quarantine_manager, provenance):
        """Test releasing quarantined content."""
        await quarantine_manager.quarantine(
            chunk_id="chunk-review",
            content="content",
            reason=QuarantineReason.MANUAL_FLAG,
            details="Manual review needed",
            provenance=provenance,
        )

        success = await quarantine_manager.review(
            chunk_id="chunk-review",
            reviewer_id="reviewer@test.com",
            decision="release",
            notes="Content verified as safe",
        )

        assert success is True

        record = await quarantine_manager.get_quarantine_record("chunk-review")
        assert record.review_status == "released"
        assert record.reviewed_by == "reviewer@test.com"

    @pytest.mark.asyncio
    async def test_review_delete(self, quarantine_manager, provenance):
        """Test deleting quarantined content."""
        await quarantine_manager.quarantine(
            chunk_id="chunk-delete",
            content="malicious content",
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Content compromised",
            provenance=provenance,
        )

        success = await quarantine_manager.review(
            chunk_id="chunk-delete",
            reviewer_id="admin@test.com",
            decision="delete",
        )

        assert success is True

        record = await quarantine_manager.get_quarantine_record("chunk-delete")
        assert record.review_status == "deleted"

    @pytest.mark.asyncio
    async def test_review_invalid_decision(self, quarantine_manager, provenance):
        """Test that invalid review decision raises error."""
        await quarantine_manager.quarantine(
            chunk_id="chunk-invalid",
            content="content",
            reason=QuarantineReason.MANUAL_FLAG,
            details="Test",
            provenance=provenance,
        )

        with pytest.raises(ValueError):
            await quarantine_manager.review(
                chunk_id="chunk-invalid",
                reviewer_id="reviewer",
                decision="invalid_decision",
            )

    @pytest.mark.asyncio
    async def test_get_pending_reviews(self, quarantine_manager, provenance):
        """Test getting pending reviews."""
        # Create multiple quarantine records
        for i in range(5):
            await quarantine_manager.quarantine(
                chunk_id=f"pending-{i}",
                content=f"content {i}",
                reason=QuarantineReason.ANOMALY_DETECTED,
                details="Anomaly found",
                provenance=provenance,
            )

        pending = await quarantine_manager.get_pending_reviews()

        assert len(pending) == 5
        assert all(r.review_status == "pending" for r in pending)

    @pytest.mark.asyncio
    async def test_get_pending_reviews_with_limit(self, quarantine_manager, provenance):
        """Test getting limited pending reviews."""
        for i in range(10):
            await quarantine_manager.quarantine(
                chunk_id=f"limited-{i}",
                content=f"content {i}",
                reason=QuarantineReason.LOW_TRUST,
                details="Low trust",
                provenance=provenance,
            )

        pending = await quarantine_manager.get_pending_reviews(limit=3)

        assert len(pending) == 3

    @pytest.mark.asyncio
    async def test_is_quarantined(self, quarantine_manager, provenance):
        """Test checking if chunk is quarantined."""
        await quarantine_manager.quarantine(
            chunk_id="quarantined-chunk",
            content="content",
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Failed",
            provenance=provenance,
        )

        assert await quarantine_manager.is_quarantined("quarantined-chunk") is True
        assert await quarantine_manager.is_quarantined("non-existent") is False

    @pytest.mark.asyncio
    async def test_get_quarantine_record(self, quarantine_manager, provenance):
        """Test getting specific quarantine record."""
        await quarantine_manager.quarantine(
            chunk_id="specific-chunk",
            content="test content",
            reason=QuarantineReason.PROVENANCE_INVALID,
            details="Invalid provenance",
            provenance=provenance,
        )

        record = await quarantine_manager.get_quarantine_record("specific-chunk")

        assert record is not None
        assert record.chunk_id == "specific-chunk"
        assert record.reason == QuarantineReason.PROVENANCE_INVALID

    @pytest.mark.asyncio
    async def test_get_quarantine_record_not_found(self, quarantine_manager):
        """Test getting non-existent quarantine record."""
        record = await quarantine_manager.get_quarantine_record("non-existent")

        assert record is None

    @pytest.mark.asyncio
    async def test_get_quarantine_stats(self, quarantine_manager, provenance):
        """Test getting quarantine statistics."""
        # Create various records
        await quarantine_manager.quarantine(
            chunk_id="stats-pending",
            content="content",
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Test",
            provenance=provenance,
        )

        await quarantine_manager.quarantine(
            chunk_id="stats-release",
            content="content",
            reason=QuarantineReason.MANUAL_FLAG,
            details="Test",
            provenance=provenance,
        )
        await quarantine_manager.review("stats-release", "reviewer", "release")

        await quarantine_manager.quarantine(
            chunk_id="stats-delete",
            content="content",
            reason=QuarantineReason.ANOMALY_DETECTED,
            details="Test",
            provenance=provenance,
        )
        await quarantine_manager.review("stats-delete", "reviewer", "delete")

        stats = await quarantine_manager.get_quarantine_stats()

        assert stats["pending"] >= 1
        assert stats["released"] >= 1
        assert stats["deleted"] >= 1
        assert stats["total"] >= 3

    @pytest.mark.asyncio
    async def test_content_hash_computed(self, quarantine_manager, provenance):
        """Test that content hash is computed correctly."""
        content = "test content for hashing"

        record = await quarantine_manager.quarantine(
            chunk_id="hash-test",
            content=content,
            reason=QuarantineReason.MANUAL_FLAG,
            details="Test",
            provenance=provenance,
        )

        import hashlib

        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        assert record.content_hash == expected_hash

    @pytest.mark.asyncio
    async def test_quarantine_preserves_provenance(
        self, quarantine_manager, provenance
    ):
        """Test that quarantine record preserves provenance."""
        record = await quarantine_manager.quarantine(
            chunk_id="provenance-test",
            content="content",
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Test",
            provenance=provenance,
        )

        assert record.provenance.repository_id == provenance.repository_id
        assert record.provenance.commit_sha == provenance.commit_sha
        assert record.provenance.author_id == provenance.author_id


class TestQuarantineManagerWithMocks:
    """Tests for QuarantineManager with mocked clients."""

    @pytest.mark.asyncio
    async def test_quarantine_with_sns_alert(self, provenance):
        """Test that SNS alert is sent on quarantine."""
        mock_sns = MagicMock()

        manager = QuarantineManager(
            sns_client=mock_sns,
            alert_topic_arn="arn:aws:sns:us-east-1:123:alert-topic",
            environment="test",
        )

        await manager.quarantine(
            chunk_id="sns-test",
            content="suspicious",
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Alert test",
            provenance=provenance,
        )

        mock_sns.publish.assert_called_once()
        call_args = mock_sns.publish.call_args
        assert call_args.kwargs["TopicArn"] == "arn:aws:sns:us-east-1:123:alert-topic"
        assert "Context Quarantine Alert" in call_args.kwargs["Subject"]


class TestQuarantineManagerSingleton:
    """Tests for global singleton management."""

    def test_get_quarantine_manager(self):
        """Test getting global manager instance."""
        manager = get_quarantine_manager()
        assert manager is not None

    def test_configure_quarantine_manager(self):
        """Test configuring global manager."""
        manager = configure_quarantine_manager(
            table_name="custom-table",
            environment="custom",
        )

        assert manager is not None
        assert "custom" in manager.table_name

    def test_reset_quarantine_manager(self):
        """Test resetting global manager."""
        manager1 = get_quarantine_manager()
        reset_quarantine_manager()
        manager2 = get_quarantine_manager()

        assert manager1 is not manager2
