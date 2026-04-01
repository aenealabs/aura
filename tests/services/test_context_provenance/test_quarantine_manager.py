"""
Tests for quarantine manager.

Tests content quarantine, HITL review workflow, and status updates.
"""

import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.services.context_provenance import (
    ProvenanceRecord,
    QuarantineManager,
    QuarantineReason,
    QuarantineRecord,
    configure_quarantine_manager,
    get_quarantine_manager,
    reset_quarantine_manager,
)


class TestQuarantineManager:
    """Test QuarantineManager class."""

    def test_initialization(self):
        """Test manager initialization."""
        manager = QuarantineManager()
        assert manager.dynamodb is None
        assert manager.neptune is None
        assert manager.opensearch is None
        assert manager.sns is None
        assert manager.environment == "dev"

    def test_initialization_with_clients(self):
        """Test manager initialization with clients."""
        dynamodb = MagicMock()
        neptune = MagicMock()
        opensearch = MagicMock()
        sns = MagicMock()

        manager = QuarantineManager(
            dynamodb_client=dynamodb,
            neptune_client=neptune,
            opensearch_client=opensearch,
            sns_client=sns,
            environment="qa",
        )

        assert manager.dynamodb is dynamodb
        assert manager.neptune is neptune
        assert manager.opensearch is opensearch
        assert manager.sns is sns
        assert manager.table_name == "aura-context-quarantine-qa"

    def test_initialization_custom_table_name(self):
        """Test manager initialization with custom table name."""
        manager = QuarantineManager(
            table_name="custom-quarantine-table",
            environment="prod",
        )
        assert manager.table_name == "custom-quarantine-table-prod"


class TestQuarantine:
    """Test quarantine method."""

    @pytest.fixture
    def manager(self):
        """Create manager for tests."""
        return QuarantineManager(environment="test")

    @pytest.fixture
    def sample_provenance(self):
        """Create sample provenance record."""
        return ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123def456",
            author_id="user-001",
            author_email="dev@example.com",
            timestamp=datetime.now(timezone.utc),
            branch="main",
            signature=None,
        )

    @pytest.mark.asyncio
    async def test_quarantine_basic(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test basic content quarantine."""
        content = "suspicious code content"

        record = await manager.quarantine(
            chunk_id="chunk-001",
            content=content,
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Hash mismatch detected",
            provenance=sample_provenance,
        )

        assert isinstance(record, QuarantineRecord)
        assert record.chunk_id == "chunk-001"
        assert record.reason == QuarantineReason.INTEGRITY_FAILURE
        assert record.details == "Hash mismatch detected"
        assert record.review_status == "pending"
        assert record.quarantined_by == "system"

    @pytest.mark.asyncio
    async def test_quarantine_content_hash(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test that content hash is computed correctly."""
        content = "test content"
        expected_hash = hashlib.sha256(content.encode()).hexdigest()

        record = await manager.quarantine(
            chunk_id="chunk-001",
            content=content,
            reason=QuarantineReason.ANOMALY_DETECTED,
            details="Test",
            provenance=sample_provenance,
        )

        assert record.content_hash == expected_hash

    @pytest.mark.asyncio
    async def test_quarantine_custom_quarantiner(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test quarantine with custom quarantined_by."""
        record = await manager.quarantine(
            chunk_id="chunk-001",
            content="content",
            reason=QuarantineReason.LOW_TRUST,
            details="Trust score below threshold",
            provenance=sample_provenance,
            quarantined_by="reviewer-001",
        )

        assert record.quarantined_by == "reviewer-001"

    @pytest.mark.asyncio
    async def test_quarantine_in_memory_storage(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test that quarantine stores in memory when no DynamoDB."""
        await manager.quarantine(
            chunk_id="chunk-mem-001",
            content="content",
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Test",
            provenance=sample_provenance,
        )

        assert "chunk-mem-001" in manager._in_memory_quarantine


class TestQuarantineWithNeptune:
    """Test quarantine with Neptune updates."""

    @pytest.fixture
    def neptune_mock(self):
        """Create mock Neptune client."""
        mock = MagicMock()
        mock.client.submit.return_value.all.return_value.result.return_value = []
        return mock

    @pytest.fixture
    def manager(self, neptune_mock):
        """Create manager with mock Neptune."""
        return QuarantineManager(neptune_client=neptune_mock, environment="test")

    @pytest.fixture
    def sample_provenance(self):
        """Create sample provenance record."""
        return ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123",
            author_id="user-001",
            author_email="dev@example.com",
            timestamp=datetime.now(timezone.utc),
            branch="main",
            signature=None,
        )

    @pytest.mark.asyncio
    async def test_quarantine_updates_neptune(
        self,
        manager: QuarantineManager,
        neptune_mock,
        sample_provenance: ProvenanceRecord,
    ):
        """Test that quarantine updates Neptune status."""
        await manager.quarantine(
            chunk_id="chunk-001",
            content="content",
            reason=QuarantineReason.ANOMALY_DETECTED,
            details="Test",
            provenance=sample_provenance,
        )

        neptune_mock.client.submit.assert_called()


class TestQuarantineWithOpenSearch:
    """Test quarantine with OpenSearch updates."""

    @pytest.fixture
    def opensearch_mock(self):
        """Create mock OpenSearch client."""
        mock = MagicMock()
        mock.update.return_value = {"result": "updated"}
        return mock

    @pytest.fixture
    def manager(self, opensearch_mock):
        """Create manager with mock OpenSearch."""
        return QuarantineManager(opensearch_client=opensearch_mock, environment="test")

    @pytest.fixture
    def sample_provenance(self):
        """Create sample provenance record."""
        return ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123",
            author_id="user-001",
            author_email="dev@example.com",
            timestamp=datetime.now(timezone.utc),
            branch="main",
            signature=None,
        )

    @pytest.mark.asyncio
    async def test_quarantine_updates_opensearch(
        self,
        manager: QuarantineManager,
        opensearch_mock,
        sample_provenance: ProvenanceRecord,
    ):
        """Test that quarantine updates OpenSearch status."""
        await manager.quarantine(
            chunk_id="chunk-001",
            content="content",
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Test",
            provenance=sample_provenance,
        )

        opensearch_mock.update.assert_called()


class TestQuarantineWithSNS:
    """Test quarantine with SNS alerts."""

    @pytest.fixture
    def sns_mock(self):
        """Create mock SNS client."""
        mock = MagicMock()
        mock.publish.return_value = {"MessageId": "msg-123"}
        return mock

    @pytest.fixture
    def manager(self, sns_mock):
        """Create manager with mock SNS."""
        return QuarantineManager(
            sns_client=sns_mock,
            alert_topic_arn="arn:aws:sns:us-east-1:123:quarantine-alerts",
            environment="test",
        )

    @pytest.fixture
    def sample_provenance(self):
        """Create sample provenance record."""
        return ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123",
            author_id="user-001",
            author_email="dev@example.com",
            timestamp=datetime.now(timezone.utc),
            branch="main",
            signature=None,
        )

    @pytest.mark.asyncio
    async def test_quarantine_sends_alert(
        self,
        manager: QuarantineManager,
        sns_mock,
        sample_provenance: ProvenanceRecord,
    ):
        """Test that quarantine sends SNS alert."""
        await manager.quarantine(
            chunk_id="chunk-001",
            content="content",
            reason=QuarantineReason.ANOMALY_DETECTED,
            details="Injection detected",
            provenance=sample_provenance,
        )

        sns_mock.publish.assert_called_once()
        call_kwargs = sns_mock.publish.call_args[1]
        assert call_kwargs["TopicArn"] == "arn:aws:sns:us-east-1:123:quarantine-alerts"
        assert "Context Quarantine Alert" in call_kwargs["Subject"]


class TestReview:
    """Test review method."""

    @pytest.fixture
    def manager(self):
        """Create manager for tests."""
        return QuarantineManager(environment="test")

    @pytest.fixture
    def sample_provenance(self):
        """Create sample provenance record."""
        return ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123",
            author_id="user-001",
            author_email="dev@example.com",
            timestamp=datetime.now(timezone.utc),
            branch="main",
            signature=None,
        )

    @pytest.mark.asyncio
    async def test_review_release(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test releasing quarantined content."""
        # First quarantine
        await manager.quarantine(
            chunk_id="chunk-001",
            content="content",
            reason=QuarantineReason.LOW_TRUST,
            details="Trust score low",
            provenance=sample_provenance,
        )

        # Then review and release
        result = await manager.review(
            chunk_id="chunk-001",
            reviewer_id="reviewer-001",
            decision="release",
            notes="False positive",
        )

        assert result is True
        record = manager._in_memory_quarantine["chunk-001"]
        assert record.review_status == "released"
        assert record.reviewed_by == "reviewer-001"

    @pytest.mark.asyncio
    async def test_review_delete(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test deleting quarantined content."""
        await manager.quarantine(
            chunk_id="chunk-002",
            content="malicious content",
            reason=QuarantineReason.ANOMALY_DETECTED,
            details="Confirmed malicious",
            provenance=sample_provenance,
        )

        result = await manager.review(
            chunk_id="chunk-002",
            reviewer_id="reviewer-001",
            decision="delete",
        )

        assert result is True
        record = manager._in_memory_quarantine["chunk-002"]
        assert record.review_status == "deleted"

    @pytest.mark.asyncio
    async def test_review_invalid_decision(self, manager: QuarantineManager):
        """Test review with invalid decision."""
        with pytest.raises(ValueError, match="Invalid decision"):
            await manager.review(
                chunk_id="chunk-001",
                reviewer_id="reviewer-001",
                decision="invalid",
            )


class TestGetPendingReviews:
    """Test get_pending_reviews method."""

    @pytest.fixture
    def manager(self):
        """Create manager for tests."""
        return QuarantineManager(environment="test")

    @pytest.fixture
    def sample_provenance(self):
        """Create sample provenance record."""
        return ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123",
            author_id="user-001",
            author_email="dev@example.com",
            timestamp=datetime.now(timezone.utc),
            branch="main",
            signature=None,
        )

    @pytest.mark.asyncio
    async def test_get_pending_reviews(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test getting pending reviews."""
        # Add some quarantined content
        for i in range(3):
            await manager.quarantine(
                chunk_id=f"chunk-{i}",
                content=f"content-{i}",
                reason=QuarantineReason.INTEGRITY_FAILURE,
                details="Test",
                provenance=sample_provenance,
            )

        pending = await manager.get_pending_reviews()
        assert len(pending) == 3

    @pytest.mark.asyncio
    async def test_get_pending_reviews_respects_limit(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test that limit is respected."""
        for i in range(10):
            await manager.quarantine(
                chunk_id=f"chunk-{i}",
                content=f"content-{i}",
                reason=QuarantineReason.INTEGRITY_FAILURE,
                details="Test",
                provenance=sample_provenance,
            )

        pending = await manager.get_pending_reviews(limit=5)
        assert len(pending) == 5


class TestGetQuarantineRecord:
    """Test get_quarantine_record method."""

    @pytest.fixture
    def manager(self):
        """Create manager for tests."""
        return QuarantineManager(environment="test")

    @pytest.fixture
    def sample_provenance(self):
        """Create sample provenance record."""
        return ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123",
            author_id="user-001",
            author_email="dev@example.com",
            timestamp=datetime.now(timezone.utc),
            branch="main",
            signature=None,
        )

    @pytest.mark.asyncio
    async def test_get_quarantine_record(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test getting a specific quarantine record."""
        await manager.quarantine(
            chunk_id="chunk-001",
            content="content",
            reason=QuarantineReason.ANOMALY_DETECTED,
            details="Test",
            provenance=sample_provenance,
        )

        record = await manager.get_quarantine_record("chunk-001")
        assert record is not None
        assert record.chunk_id == "chunk-001"

    @pytest.mark.asyncio
    async def test_get_quarantine_record_not_found(self, manager: QuarantineManager):
        """Test getting non-existent record."""
        record = await manager.get_quarantine_record("non-existent")
        assert record is None


class TestIsQuarantined:
    """Test is_quarantined method."""

    @pytest.fixture
    def manager(self):
        """Create manager for tests."""
        return QuarantineManager(environment="test")

    @pytest.fixture
    def sample_provenance(self):
        """Create sample provenance record."""
        return ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123",
            author_id="user-001",
            author_email="dev@example.com",
            timestamp=datetime.now(timezone.utc),
            branch="main",
            signature=None,
        )

    @pytest.mark.asyncio
    async def test_is_quarantined_true(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test checking quarantined content."""
        await manager.quarantine(
            chunk_id="chunk-001",
            content="content",
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Test",
            provenance=sample_provenance,
        )

        assert await manager.is_quarantined("chunk-001") is True

    @pytest.mark.asyncio
    async def test_is_quarantined_false_not_found(self, manager: QuarantineManager):
        """Test checking non-quarantined content."""
        assert await manager.is_quarantined("non-existent") is False

    @pytest.mark.asyncio
    async def test_is_quarantined_false_released(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test checking released content."""
        await manager.quarantine(
            chunk_id="chunk-001",
            content="content",
            reason=QuarantineReason.LOW_TRUST,
            details="Test",
            provenance=sample_provenance,
        )
        await manager.review(
            chunk_id="chunk-001",
            reviewer_id="reviewer",
            decision="release",
        )

        assert await manager.is_quarantined("chunk-001") is False


class TestGetQuarantineStats:
    """Test get_quarantine_stats method."""

    @pytest.fixture
    def manager(self):
        """Create manager for tests."""
        return QuarantineManager(environment="test")

    @pytest.fixture
    def sample_provenance(self):
        """Create sample provenance record."""
        return ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123",
            author_id="user-001",
            author_email="dev@example.com",
            timestamp=datetime.now(timezone.utc),
            branch="main",
            signature=None,
        )

    @pytest.mark.asyncio
    async def test_get_quarantine_stats_empty(self, manager: QuarantineManager):
        """Test getting stats with no records."""
        stats = await manager.get_quarantine_stats()
        assert stats["pending"] == 0
        assert stats["released"] == 0
        assert stats["deleted"] == 0
        assert stats["total"] == 0

    @pytest.mark.asyncio
    async def test_get_quarantine_stats_with_records(
        self,
        manager: QuarantineManager,
        sample_provenance: ProvenanceRecord,
    ):
        """Test getting stats with records."""
        # Add pending records
        for i in range(3):
            await manager.quarantine(
                chunk_id=f"pending-{i}",
                content=f"content-{i}",
                reason=QuarantineReason.INTEGRITY_FAILURE,
                details="Test",
                provenance=sample_provenance,
            )

        # Add and release one
        await manager.quarantine(
            chunk_id="released-0",
            content="content",
            reason=QuarantineReason.LOW_TRUST,
            details="Test",
            provenance=sample_provenance,
        )
        await manager.review("released-0", "reviewer", "release")

        stats = await manager.get_quarantine_stats()
        assert stats["pending"] == 3
        assert stats["released"] == 1
        assert stats["total"] == 4


class TestSingletonFunctions:
    """Test singleton management functions."""

    def test_get_quarantine_manager(self):
        """Test get_quarantine_manager returns singleton."""
        manager1 = get_quarantine_manager()
        manager2 = get_quarantine_manager()
        assert manager1 is manager2

    def test_reset_quarantine_manager(self):
        """Test reset_quarantine_manager creates new instance."""
        manager1 = get_quarantine_manager()
        reset_quarantine_manager()
        manager2 = get_quarantine_manager()
        assert manager1 is not manager2

    def test_configure_quarantine_manager(self):
        """Test configure_quarantine_manager."""
        dynamodb = MagicMock()
        neptune = MagicMock()
        opensearch = MagicMock()
        sns = MagicMock()

        manager = configure_quarantine_manager(
            dynamodb_client=dynamodb,
            neptune_client=neptune,
            opensearch_client=opensearch,
            sns_client=sns,
            table_name="custom-table",
            alert_topic_arn="arn:aws:sns:us-east-1:123:alerts",
            environment="prod",
        )

        assert manager.dynamodb is dynamodb
        assert manager.neptune is neptune
        assert manager.opensearch is opensearch
        assert manager.sns is sns
        assert manager.table_name == "custom-table-prod"
        assert manager.alert_topic == "arn:aws:sns:us-east-1:123:alerts"
