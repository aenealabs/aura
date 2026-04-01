"""
Tests for ADR-080 Phase 5: Advanced Memory Evolution Operations.

Tests cover:
- LINK operation: Neptune graph edge creation
- CORRECT operation: LLM-verified memory correction
- ROLLBACK operation: Snapshot-based memory restoration
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.services.memory_evolution.advanced_operations import (
    AdvancedOperationsConfig,
    CorrectionCandidate,
    CorrectionReason,
    CorrectionResult,
    CorrectOperationService,
    LinkCandidate,
    LinkResult,
    LinkType,
    MemoryLinkService,
    RollbackOperationService,
    RollbackResult,
    SnapshotMetadata,
    SnapshotSource,
    get_correct_service,
    get_link_service,
    get_rollback_service,
    reset_correct_service,
    reset_link_service,
    reset_rollback_service,
)
from src.services.memory_evolution.contracts import (
    MemorySnapshot,
    RefineAction,
    RefineOperation,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before and after each test."""
    reset_link_service()
    reset_correct_service()
    reset_rollback_service()
    yield
    reset_link_service()
    reset_correct_service()
    reset_rollback_service()


@pytest.fixture
def mock_neptune_service():
    """Create a mock Neptune service."""
    service = AsyncMock()
    service.execute_gremlin = AsyncMock(return_value={"result": "success"})
    service.vertex_exists = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_memory_store():
    """Create a mock memory store."""
    store = AsyncMock()
    store.get_memory = AsyncMock(
        return_value={
            "memory_id": "mem-123",
            "content": "Original content",
            "tenant_id": "tenant-1",
            "security_domain": "domain-1",
            "version": 1,
        }
    )
    store.update_memory = AsyncMock(
        return_value={
            "memory_id": "mem-123",
            "content": "Corrected content",
            "version": 2,
        }
    )
    store.get_memory_version = AsyncMock(return_value=1)
    store.restore_memories = AsyncMock(return_value=(5, []))
    return store


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    service = AsyncMock()
    service.verify_correction = AsyncMock(
        return_value=(True, 0.95, "Correction is valid")
    )
    service.detect_inconsistency = AsyncMock(
        return_value=(False, 0.9, "No inconsistency detected")
    )
    return service


@pytest.fixture
def mock_snapshot_store():
    """Create a mock snapshot store."""
    store = AsyncMock()
    store.save_snapshot = AsyncMock(return_value="snap-abc123")
    store.get_snapshot = AsyncMock(
        return_value=MemorySnapshot(
            snapshot_id="snap-abc123",
            memory_ids=["mem-1", "mem-2"],
            snapshot_data={
                "mem-1": {"content": "Content 1", "security_domain": "domain-1"},
                "mem-2": {"content": "Content 2", "security_domain": "domain-1"},
            },
            tenant_id="tenant-1",
            security_domain="domain-1",
        )
    )
    store.list_snapshots = AsyncMock(return_value=[])
    store.delete_snapshot = AsyncMock(return_value=True)
    return store


@pytest.fixture
def default_config():
    """Create default configuration."""
    return AdvancedOperationsConfig()


@pytest.fixture
def link_action():
    """Create a sample LINK action."""
    return RefineAction(
        operation=RefineOperation.LINK,
        target_memory_ids=["mem-1", "mem-2"],
        reasoning="Creating strategy link",
        confidence=0.85,
        tenant_id="tenant-1",
        security_domain="domain-1",
        action_id="action-link-1",
        metadata={"link_type": "STRATEGY_DERIVED_FROM"},
    )


@pytest.fixture
def correct_action():
    """Create a sample CORRECT action."""
    return RefineAction(
        operation=RefineOperation.CORRECT,
        target_memory_ids=["mem-123"],
        reasoning="Fixing factual error",
        confidence=0.9,
        tenant_id="tenant-1",
        security_domain="domain-1",
        action_id="action-correct-1",
        metadata={
            "corrected_content": "Corrected content",
            "correction_reason": "factual_error",
        },
    )


@pytest.fixture
def rollback_action():
    """Create a sample ROLLBACK action."""
    return RefineAction(
        operation=RefineOperation.ROLLBACK,
        target_memory_ids=["mem-1", "mem-2"],
        reasoning="Reverting failed consolidation",
        confidence=1.0,
        tenant_id="tenant-1",
        security_domain="domain-1",
        action_id="action-rollback-1",
        metadata={"snapshot_id": "snap-abc123"},
    )


# =============================================================================
# LINK TYPE ENUM TESTS
# =============================================================================


class TestLinkType:
    """Tests for LinkType enum."""

    def test_all_link_types_defined(self):
        """Verify all link types are defined."""
        assert LinkType.STRATEGY_DERIVED_FROM.value == "STRATEGY_DERIVED_FROM"
        assert LinkType.REINFORCES.value == "REINFORCES"
        assert LinkType.CONTRADICTS.value == "CONTRADICTS"
        assert LinkType.SUPERSEDES.value == "SUPERSEDES"
        assert LinkType.RELATED_TO.value == "RELATED_TO"
        assert LinkType.DEPENDS_ON.value == "DEPENDS_ON"
        assert LinkType.SIMILAR_TO.value == "SIMILAR_TO"

    def test_link_type_count(self):
        """Verify expected number of link types."""
        assert len(LinkType) == 7


class TestCorrectionReason:
    """Tests for CorrectionReason enum."""

    def test_all_correction_reasons_defined(self):
        """Verify all correction reasons are defined."""
        assert CorrectionReason.FACTUAL_ERROR.value == "factual_error"
        assert CorrectionReason.OUTDATED_INFO.value == "outdated_info"
        assert CorrectionReason.MISATTRIBUTION.value == "misattribution"
        assert CorrectionReason.STRATEGY_FAILURE.value == "strategy_failure"
        assert CorrectionReason.USER_FEEDBACK.value == "user_feedback"
        assert CorrectionReason.LLM_VERIFICATION.value == "llm_verification"


class TestSnapshotSource:
    """Tests for SnapshotSource enum."""

    def test_all_snapshot_sources_defined(self):
        """Verify all snapshot sources are defined."""
        assert SnapshotSource.DYNAMODB_STREAMS.value == "dynamodb_streams"
        assert SnapshotSource.POINT_IN_TIME.value == "point_in_time"
        assert SnapshotSource.MANUAL_BACKUP.value == "manual_backup"
        assert SnapshotSource.PRE_OPERATION.value == "pre_operation"


# =============================================================================
# LINK CANDIDATE TESTS
# =============================================================================


class TestLinkCandidate:
    """Tests for LinkCandidate dataclass."""

    def test_valid_link_candidate(self):
        """Test creating a valid link candidate."""
        candidate = LinkCandidate(
            source_memory_id="mem-1",
            target_memory_id="mem-2",
            link_type=LinkType.REINFORCES,
            confidence=0.85,
            reasoning="Strong pattern match",
        )
        assert candidate.source_memory_id == "mem-1"
        assert candidate.target_memory_id == "mem-2"
        assert candidate.link_type == LinkType.REINFORCES
        assert candidate.confidence == 0.85

    def test_invalid_confidence_raises(self):
        """Test that invalid confidence raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            LinkCandidate(
                source_memory_id="mem-1",
                target_memory_id="mem-2",
                link_type=LinkType.RELATED_TO,
                confidence=1.5,
                reasoning="Test",
            )

    def test_self_link_raises(self):
        """Test that linking memory to itself raises ValueError."""
        with pytest.raises(ValueError, match="Cannot link memory to itself"):
            LinkCandidate(
                source_memory_id="mem-1",
                target_memory_id="mem-1",
                link_type=LinkType.RELATED_TO,
                confidence=0.8,
                reasoning="Test",
            )

    def test_to_dict(self):
        """Test serialization to dictionary."""
        candidate = LinkCandidate(
            source_memory_id="mem-1",
            target_memory_id="mem-2",
            link_type=LinkType.CONTRADICTS,
            confidence=0.7,
            reasoning="Conflicting info",
            bidirectional=True,
        )
        d = candidate.to_dict()
        assert d["source_memory_id"] == "mem-1"
        assert d["target_memory_id"] == "mem-2"
        assert d["link_type"] == "CONTRADICTS"
        assert d["bidirectional"] is True


# =============================================================================
# CORRECTION CANDIDATE TESTS
# =============================================================================


class TestCorrectionCandidate:
    """Tests for CorrectionCandidate dataclass."""

    def test_valid_correction_candidate(self):
        """Test creating a valid correction candidate."""
        candidate = CorrectionCandidate(
            memory_id="mem-123",
            correction_reason=CorrectionReason.FACTUAL_ERROR,
            original_content="Python 2 is current",
            corrected_content="Python 3 is current",
            verification_confidence=0.95,
        )
        assert candidate.memory_id == "mem-123"
        assert candidate.correction_reason == CorrectionReason.FACTUAL_ERROR
        assert candidate.verification_confidence == 0.95

    def test_invalid_confidence_raises(self):
        """Test that invalid confidence raises ValueError."""
        with pytest.raises(ValueError, match="Verification confidence must be"):
            CorrectionCandidate(
                memory_id="mem-123",
                correction_reason=CorrectionReason.OUTDATED_INFO,
                original_content="Old",
                corrected_content="New",
                verification_confidence=-0.1,
            )

    def test_to_dict(self):
        """Test serialization to dictionary."""
        candidate = CorrectionCandidate(
            memory_id="mem-123",
            correction_reason=CorrectionReason.USER_FEEDBACK,
            original_content="Wrong",
            corrected_content="Right",
            verification_confidence=0.9,
            supporting_evidence=["User report #456"],
            requires_human_review=True,
        )
        d = candidate.to_dict()
        assert d["memory_id"] == "mem-123"
        assert d["correction_reason"] == "user_feedback"
        assert d["requires_human_review"] is True
        assert len(d["supporting_evidence"]) == 1


# =============================================================================
# SNAPSHOT METADATA TESTS
# =============================================================================


class TestSnapshotMetadata:
    """Tests for SnapshotMetadata dataclass."""

    def test_valid_snapshot_metadata(self):
        """Test creating valid snapshot metadata."""
        now = datetime.now(timezone.utc)
        metadata = SnapshotMetadata(
            snapshot_id="snap-abc123",
            source=SnapshotSource.PRE_OPERATION,
            memory_count=5,
            created_at=now,
            operation_id="op-123",
        )
        assert metadata.snapshot_id == "snap-abc123"
        assert metadata.source == SnapshotSource.PRE_OPERATION
        assert metadata.memory_count == 5

    def test_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=30)
        metadata = SnapshotMetadata(
            snapshot_id="snap-xyz",
            source=SnapshotSource.DYNAMODB_STREAMS,
            memory_count=10,
            created_at=now,
            expires_at=expires,
            stream_sequence_number="seq-12345",
        )
        d = metadata.to_dict()
        assert d["snapshot_id"] == "snap-xyz"
        assert d["source"] == "dynamodb_streams"
        assert d["stream_sequence_number"] == "seq-12345"


# =============================================================================
# LINK RESULT TESTS
# =============================================================================


class TestLinkResult:
    """Tests for LinkResult dataclass."""

    def test_valid_link_result(self):
        """Test creating a valid link result."""
        result = LinkResult(
            edge_id="edge-123",
            source_memory_id="mem-1",
            target_memory_id="mem-2",
            link_type=LinkType.REINFORCES,
        )
        assert result.edge_id == "edge-123"
        assert result.link_type == LinkType.REINFORCES

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = LinkResult(
            edge_id="edge-456",
            source_memory_id="mem-a",
            target_memory_id="mem-b",
            link_type=LinkType.SUPERSEDES,
        )
        d = result.to_dict()
        assert d["edge_id"] == "edge-456"
        assert d["link_type"] == "SUPERSEDES"
        assert "created_at" in d


# =============================================================================
# CORRECTION RESULT TESTS
# =============================================================================


class TestCorrectionResult:
    """Tests for CorrectionResult dataclass."""

    def test_valid_correction_result(self):
        """Test creating a valid correction result."""
        result = CorrectionResult(
            memory_id="mem-123",
            version_before=1,
            version_after=2,
            correction_reason=CorrectionReason.FACTUAL_ERROR,
            human_review_required=False,
        )
        assert result.version_before == 1
        assert result.version_after == 2

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = CorrectionResult(
            memory_id="mem-456",
            version_before=3,
            version_after=4,
            correction_reason=CorrectionReason.STRATEGY_FAILURE,
            human_review_required=True,
        )
        d = result.to_dict()
        assert d["correction_reason"] == "strategy_failure"
        assert d["human_review_required"] is True


# =============================================================================
# ROLLBACK RESULT TESTS
# =============================================================================


class TestRollbackResult:
    """Tests for RollbackResult dataclass."""

    def test_valid_rollback_result(self):
        """Test creating a valid rollback result."""
        result = RollbackResult(
            snapshot_id="snap-abc",
            memories_restored=5,
            memories_failed=0,
        )
        assert result.memories_restored == 5
        assert result.memories_failed == 0

    def test_rollback_result_with_failures(self):
        """Test rollback result with some failures."""
        result = RollbackResult(
            snapshot_id="snap-xyz",
            memories_restored=3,
            memories_failed=2,
            failed_memory_ids=["mem-4", "mem-5"],
        )
        assert len(result.failed_memory_ids) == 2

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = RollbackResult(
            snapshot_id="snap-123",
            memories_restored=10,
            memories_failed=1,
            failed_memory_ids=["mem-bad"],
        )
        d = result.to_dict()
        assert d["snapshot_id"] == "snap-123"
        assert d["memories_restored"] == 10


# =============================================================================
# ADVANCED OPERATIONS CONFIG TESTS
# =============================================================================


class TestAdvancedOperationsConfig:
    """Tests for AdvancedOperationsConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AdvancedOperationsConfig()
        assert config.link_confidence_threshold == 0.7
        assert config.max_links_per_memory == 50
        assert config.correction_confidence_threshold == 0.8
        assert config.human_review_threshold == 0.6
        assert config.snapshot_retention_days == 30
        assert config.max_memories_per_rollback == 100
        assert config.link_enabled is True
        assert config.correct_enabled is True
        assert config.rollback_enabled is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = AdvancedOperationsConfig(
            link_confidence_threshold=0.9,
            max_links_per_memory=100,
            link_enabled=False,
        )
        assert config.link_confidence_threshold == 0.9
        assert config.max_links_per_memory == 100
        assert config.link_enabled is False


# =============================================================================
# MEMORY LINK SERVICE TESTS
# =============================================================================


class TestMemoryLinkService:
    """Tests for MemoryLinkService."""

    @pytest.mark.asyncio
    async def test_link_success(self, mock_neptune_service, link_action):
        """Test successful link creation."""
        service = MemoryLinkService(mock_neptune_service)
        result = await service.link(link_action)

        assert result.success is True
        assert result.operation == RefineOperation.LINK
        assert len(result.affected_memory_ids) == 2
        assert result.rollback_token is not None
        assert "edge:" in result.rollback_token

    @pytest.mark.asyncio
    async def test_link_disabled(self, mock_neptune_service, link_action):
        """Test link when disabled."""
        config = AdvancedOperationsConfig(link_enabled=False)
        service = MemoryLinkService(mock_neptune_service, config)
        result = await service.link(link_action)

        assert result.success is False
        assert "disabled" in result.error

    @pytest.mark.asyncio
    async def test_link_wrong_operation(self, mock_neptune_service, correct_action):
        """Test link with wrong operation type."""
        service = MemoryLinkService(mock_neptune_service)
        with pytest.raises(Exception):
            await service.link(correct_action)

    @pytest.mark.asyncio
    async def test_link_wrong_memory_count(self, mock_neptune_service):
        """Test link with wrong number of memory IDs."""
        service = MemoryLinkService(mock_neptune_service)
        action = RefineAction(
            operation=RefineOperation.LINK,
            target_memory_ids=["mem-1"],  # Only 1 ID
            reasoning="Test",
            confidence=0.8,
            tenant_id="tenant-1",
            security_domain="domain-1",
        )
        with pytest.raises(Exception):
            await service.link(action)

    @pytest.mark.asyncio
    async def test_link_vertex_not_found(self, mock_neptune_service, link_action):
        """Test link when vertex doesn't exist."""
        mock_neptune_service.vertex_exists = AsyncMock(return_value=False)
        service = MemoryLinkService(mock_neptune_service)
        result = await service.link(link_action)

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_link_bidirectional(self, mock_neptune_service):
        """Test bidirectional link creation."""
        action = RefineAction(
            operation=RefineOperation.LINK,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Bidirectional relationship",
            confidence=0.9,
            tenant_id="tenant-1",
            security_domain="domain-1",
            metadata={"link_type": "SIMILAR_TO", "bidirectional": True},
        )
        service = MemoryLinkService(mock_neptune_service)
        result = await service.link(action)

        assert result.success is True
        # Should have called execute_gremlin twice for bidirectional
        assert mock_neptune_service.execute_gremlin.call_count == 2

    @pytest.mark.asyncio
    async def test_remove_link(self, mock_neptune_service):
        """Test link removal."""
        service = MemoryLinkService(mock_neptune_service)
        result = await service.remove_link(
            source_id="mem-1",
            target_id="mem-2",
            link_type=LinkType.REINFORCES,
            tenant_id="tenant-1",
            security_domain="domain-1",
        )
        assert result is True
        mock_neptune_service.execute_gremlin.assert_called_once()


# =============================================================================
# CORRECT OPERATION SERVICE TESTS
# =============================================================================


class TestCorrectOperationService:
    """Tests for CorrectOperationService."""

    @pytest.mark.asyncio
    async def test_correct_success(
        self, mock_memory_store, mock_llm_service, correct_action
    ):
        """Test successful correction."""
        service = CorrectOperationService(mock_memory_store, mock_llm_service)
        result = await service.correct(correct_action)

        assert result.success is True
        assert result.operation == RefineOperation.CORRECT
        assert "mem-123" in result.affected_memory_ids
        assert result.metrics["version_before"] == 1
        assert result.metrics["version_after"] == 2

    @pytest.mark.asyncio
    async def test_correct_disabled(
        self, mock_memory_store, mock_llm_service, correct_action
    ):
        """Test correct when disabled."""
        config = AdvancedOperationsConfig(correct_enabled=False)
        service = CorrectOperationService(mock_memory_store, mock_llm_service, config)
        result = await service.correct(correct_action)

        assert result.success is False
        assert "disabled" in result.error

    @pytest.mark.asyncio
    async def test_correct_memory_not_found(
        self, mock_memory_store, mock_llm_service, correct_action
    ):
        """Test correct when memory doesn't exist."""
        mock_memory_store.get_memory = AsyncMock(return_value=None)
        service = CorrectOperationService(mock_memory_store, mock_llm_service)
        result = await service.correct(correct_action)

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_correct_security_domain_mismatch(
        self, mock_memory_store, mock_llm_service, correct_action
    ):
        """Test correct fails with security domain mismatch."""
        mock_memory_store.get_memory = AsyncMock(
            return_value={
                "memory_id": "mem-123",
                "content": "Original",
                "security_domain": "different-domain",
            }
        )
        service = CorrectOperationService(mock_memory_store, mock_llm_service)
        result = await service.correct(correct_action)

        assert result.success is False
        assert "security domain" in result.error.lower()

    @pytest.mark.asyncio
    async def test_correct_requires_human_review(
        self, mock_memory_store, mock_llm_service, correct_action
    ):
        """Test correct requires human review for low confidence."""
        mock_llm_service.verify_correction = AsyncMock(
            return_value=(True, 0.5, "Low confidence correction")
        )
        correct_action.confidence = 0.8  # Below 0.95 threshold

        service = CorrectOperationService(mock_memory_store, mock_llm_service)
        result = await service.correct(correct_action)

        assert result.success is False
        assert "human review" in result.error.lower()

    @pytest.mark.asyncio
    async def test_correct_rejected_by_llm(
        self, mock_memory_store, mock_llm_service, correct_action
    ):
        """Test correct rejected by LLM verification."""
        mock_llm_service.verify_correction = AsyncMock(
            return_value=(False, 0.9, "Correction introduces new errors")
        )
        service = CorrectOperationService(mock_memory_store, mock_llm_service)
        result = await service.correct(correct_action)

        assert result.success is False
        assert "rejected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_correct_missing_content(self, mock_memory_store, mock_llm_service):
        """Test correct fails without corrected content."""
        action = RefineAction(
            operation=RefineOperation.CORRECT,
            target_memory_ids=["mem-123"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-1",
            security_domain="domain-1",
            metadata={},  # Missing corrected_content
        )
        service = CorrectOperationService(mock_memory_store, mock_llm_service)
        with pytest.raises(Exception, match="corrected_content"):
            await service.correct(action)

    @pytest.mark.asyncio
    async def test_detect_corrections_needed(self, mock_memory_store, mock_llm_service):
        """Test detection of corrections needed."""
        mock_llm_service.detect_inconsistency = AsyncMock(
            return_value=(True, 0.85, "Found factual inconsistency")
        )
        service = CorrectOperationService(mock_memory_store, mock_llm_service)

        candidates = await service.detect_corrections_needed(
            memory_ids=["mem-1", "mem-2"],
            tenant_id="tenant-1",
            context_memories=[{"content": "Context 1"}, {"content": "Context 2"}],
        )

        assert len(candidates) == 2
        assert all(
            c.correction_reason == CorrectionReason.LLM_VERIFICATION for c in candidates
        )


# =============================================================================
# ROLLBACK OPERATION SERVICE TESTS
# =============================================================================


class TestRollbackOperationService:
    """Tests for RollbackOperationService."""

    @pytest.mark.asyncio
    async def test_rollback_success(
        self, mock_memory_store, mock_snapshot_store, rollback_action
    ):
        """Test successful rollback."""
        service = RollbackOperationService(mock_memory_store, mock_snapshot_store)
        result = await service.rollback(rollback_action)

        assert result.success is True
        assert result.operation == RefineOperation.ROLLBACK
        assert result.metrics["memories_restored"] == 5
        assert result.metrics["memories_failed"] == 0

    @pytest.mark.asyncio
    async def test_rollback_disabled(
        self, mock_memory_store, mock_snapshot_store, rollback_action
    ):
        """Test rollback when disabled."""
        config = AdvancedOperationsConfig(rollback_enabled=False)
        service = RollbackOperationService(
            mock_memory_store, mock_snapshot_store, config
        )
        result = await service.rollback(rollback_action)

        assert result.success is False
        assert "disabled" in result.error

    @pytest.mark.asyncio
    async def test_rollback_snapshot_not_found(
        self, mock_memory_store, mock_snapshot_store, rollback_action
    ):
        """Test rollback when snapshot doesn't exist."""
        mock_snapshot_store.get_snapshot = AsyncMock(return_value=None)
        service = RollbackOperationService(mock_memory_store, mock_snapshot_store)
        result = await service.rollback(rollback_action)

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_rollback_tenant_mismatch(
        self, mock_memory_store, mock_snapshot_store, rollback_action
    ):
        """Test rollback fails with tenant mismatch."""
        mock_snapshot_store.get_snapshot = AsyncMock(
            return_value=MemorySnapshot(
                snapshot_id="snap-abc123",
                memory_ids=["mem-1"],
                snapshot_data={},
                tenant_id="different-tenant",
                security_domain="domain-1",
            )
        )
        service = RollbackOperationService(mock_memory_store, mock_snapshot_store)
        result = await service.rollback(rollback_action)

        assert result.success is False
        assert "tenant" in result.error.lower()

    @pytest.mark.asyncio
    async def test_rollback_security_domain_mismatch(
        self, mock_memory_store, mock_snapshot_store, rollback_action
    ):
        """Test rollback fails with security domain mismatch."""
        mock_snapshot_store.get_snapshot = AsyncMock(
            return_value=MemorySnapshot(
                snapshot_id="snap-abc123",
                memory_ids=["mem-1"],
                snapshot_data={},
                tenant_id="tenant-1",
                security_domain="different-domain",
            )
        )
        service = RollbackOperationService(mock_memory_store, mock_snapshot_store)
        result = await service.rollback(rollback_action)

        assert result.success is False
        assert "security domain" in result.error.lower()

    @pytest.mark.asyncio
    async def test_rollback_exceeds_memory_limit(
        self, mock_memory_store, mock_snapshot_store, rollback_action
    ):
        """Test rollback fails when exceeding memory limit."""
        config = AdvancedOperationsConfig(max_memories_per_rollback=1)
        mock_snapshot_store.get_snapshot = AsyncMock(
            return_value=MemorySnapshot(
                snapshot_id="snap-abc123",
                memory_ids=["mem-1", "mem-2"],  # 2 > limit of 1
                snapshot_data={"mem-1": {}, "mem-2": {}},
                tenant_id="tenant-1",
                security_domain="domain-1",
            )
        )
        service = RollbackOperationService(
            mock_memory_store, mock_snapshot_store, config
        )
        result = await service.rollback(rollback_action)

        assert result.success is False
        assert "exceeds limit" in result.error.lower()

    @pytest.mark.asyncio
    async def test_rollback_with_failures(
        self, mock_memory_store, mock_snapshot_store, rollback_action
    ):
        """Test rollback with some restore failures."""
        mock_memory_store.restore_memories = AsyncMock(
            return_value=(3, ["mem-2"])  # 3 restored, 1 failed
        )
        service = RollbackOperationService(mock_memory_store, mock_snapshot_store)
        result = await service.rollback(rollback_action)

        assert result.success is False
        assert result.metrics["memories_restored"] == 3
        assert result.metrics["memories_failed"] == 1

    @pytest.mark.asyncio
    async def test_rollback_from_token(self, mock_memory_store, mock_snapshot_store):
        """Test rollback using rollback_token instead of snapshot_id."""
        action = RefineAction(
            operation=RefineOperation.ROLLBACK,
            target_memory_ids=["mem-1"],
            reasoning="Test",
            confidence=1.0,
            tenant_id="tenant-1",
            security_domain="domain-1",
            metadata={"rollback_token": "snapshot:snap-abc123"},
        )
        service = RollbackOperationService(mock_memory_store, mock_snapshot_store)
        result = await service.rollback(action)

        assert result.success is True
        mock_snapshot_store.get_snapshot.assert_called_with(
            "snap-abc123", "tenant-1", "domain-1"
        )

    @pytest.mark.asyncio
    async def test_create_snapshot(self, mock_memory_store, mock_snapshot_store):
        """Test snapshot creation."""
        service = RollbackOperationService(mock_memory_store, mock_snapshot_store)
        snapshot = await service.create_snapshot(
            memory_ids=["mem-1", "mem-2"],
            tenant_id="tenant-1",
            security_domain="domain-1",
            operation_id="op-123",
        )

        assert snapshot.snapshot_id.startswith("snap-")
        assert len(snapshot.memory_ids) == 2
        mock_snapshot_store.save_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_available_snapshots(
        self, mock_memory_store, mock_snapshot_store
    ):
        """Test listing available snapshots."""
        service = RollbackOperationService(mock_memory_store, mock_snapshot_store)
        snapshots = await service.list_available_snapshots(
            tenant_id="tenant-1",
            security_domain="domain-1",
            limit=5,
        )

        mock_snapshot_store.list_snapshots.assert_called_once_with(
            "tenant-1", "domain-1", 5
        )


# =============================================================================
# SINGLETON MANAGEMENT TESTS
# =============================================================================


class TestSingletonManagement:
    """Tests for singleton getter/reset functions."""

    def test_get_link_service_requires_neptune(self):
        """Test that get_link_service requires neptune_service."""
        with pytest.raises(ValueError, match="neptune_service is required"):
            get_link_service()

    def test_get_link_service_creates_singleton(self, mock_neptune_service):
        """Test that get_link_service creates and returns singleton."""
        service1 = get_link_service(mock_neptune_service)
        service2 = get_link_service()  # Should return same instance
        assert service1 is service2

    def test_reset_link_service(self, mock_neptune_service):
        """Test that reset_link_service clears singleton."""
        service1 = get_link_service(mock_neptune_service)
        reset_link_service()
        service2 = get_link_service(mock_neptune_service)
        assert service1 is not service2

    def test_get_correct_service_requires_dependencies(self):
        """Test that get_correct_service requires dependencies."""
        with pytest.raises(ValueError, match="memory_store and llm_service"):
            get_correct_service()

    def test_get_correct_service_creates_singleton(
        self, mock_memory_store, mock_llm_service
    ):
        """Test that get_correct_service creates and returns singleton."""
        service1 = get_correct_service(mock_memory_store, mock_llm_service)
        service2 = get_correct_service()
        assert service1 is service2

    def test_reset_correct_service(self, mock_memory_store, mock_llm_service):
        """Test that reset_correct_service clears singleton."""
        service1 = get_correct_service(mock_memory_store, mock_llm_service)
        reset_correct_service()
        service2 = get_correct_service(mock_memory_store, mock_llm_service)
        assert service1 is not service2

    def test_get_rollback_service_requires_dependencies(self):
        """Test that get_rollback_service requires dependencies."""
        with pytest.raises(ValueError, match="memory_store and snapshot_store"):
            get_rollback_service()

    def test_get_rollback_service_creates_singleton(
        self, mock_memory_store, mock_snapshot_store
    ):
        """Test that get_rollback_service creates and returns singleton."""
        service1 = get_rollback_service(mock_memory_store, mock_snapshot_store)
        service2 = get_rollback_service()
        assert service1 is service2

    def test_reset_rollback_service(self, mock_memory_store, mock_snapshot_store):
        """Test that reset_rollback_service clears singleton."""
        service1 = get_rollback_service(mock_memory_store, mock_snapshot_store)
        reset_rollback_service()
        service2 = get_rollback_service(mock_memory_store, mock_snapshot_store)
        assert service1 is not service2
