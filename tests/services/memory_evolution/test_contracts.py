"""Tests for memory evolution contracts."""

from datetime import datetime, timezone

import pytest

from src.services.memory_evolution import (
    ConsolidationCandidate,
    EvolutionRecord,
    MemorySnapshot,
    OperationPhase,
    PruneCandidate,
    RefineAction,
    RefineOperation,
    RefineResult,
    SimilarityMetric,
)


class TestRefineOperation:
    """Tests for RefineOperation enum."""

    def test_all_operations_defined(self):
        """Verify all expected operations are defined."""
        operations = [op.value for op in RefineOperation]
        assert "consolidate" in operations
        assert "prune" in operations
        assert "reinforce" in operations
        assert "abstract" in operations
        assert "link" in operations
        assert "correct" in operations
        assert "rollback" in operations

    def test_operation_from_string(self):
        """Test creating operation from string value."""
        assert RefineOperation("consolidate") == RefineOperation.CONSOLIDATE
        assert RefineOperation("prune") == RefineOperation.PRUNE

    def test_invalid_operation_raises(self):
        """Test invalid operation string raises ValueError."""
        with pytest.raises(ValueError):
            RefineOperation("invalid_operation")


class TestOperationPhase:
    """Tests for OperationPhase enum."""

    def test_phase_mapping(self):
        """Verify operations are mapped to correct phases."""
        assert (
            OperationPhase.get_phase(RefineOperation.CONSOLIDATE)
            == OperationPhase.PHASE_1A
        )
        assert (
            OperationPhase.get_phase(RefineOperation.PRUNE) == OperationPhase.PHASE_1A
        )
        assert (
            OperationPhase.get_phase(RefineOperation.REINFORCE)
            == OperationPhase.PHASE_1B
        )
        assert (
            OperationPhase.get_phase(RefineOperation.ABSTRACT) == OperationPhase.PHASE_3
        )
        assert OperationPhase.get_phase(RefineOperation.LINK) == OperationPhase.PHASE_5
        assert (
            OperationPhase.get_phase(RefineOperation.CORRECT) == OperationPhase.PHASE_5
        )
        assert (
            OperationPhase.get_phase(RefineOperation.ROLLBACK) == OperationPhase.PHASE_5
        )


class TestRefineAction:
    """Tests for RefineAction dataclass."""

    def test_create_valid_action(self):
        """Test creating a valid refine action."""
        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Similar patterns",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )
        assert action.operation == RefineOperation.CONSOLIDATE
        assert len(action.target_memory_ids) == 2
        assert action.confidence == 0.9
        assert action.tenant_id == "tenant-123"

    def test_confidence_validation(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            RefineAction(
                operation=RefineOperation.CONSOLIDATE,
                target_memory_ids=["mem-1"],
                reasoning="Test",
                confidence=1.5,  # Invalid
                tenant_id="tenant-123",
                security_domain="development",
            )

    def test_confidence_validation_negative(self):
        """Test confidence cannot be negative."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            RefineAction(
                operation=RefineOperation.CONSOLIDATE,
                target_memory_ids=["mem-1"],
                reasoning="Test",
                confidence=-0.1,  # Invalid
                tenant_id="tenant-123",
                security_domain="development",
            )

    def test_target_memory_ids_required(self):
        """Test at least one target memory ID is required."""
        with pytest.raises(ValueError, match="At least one target memory ID"):
            RefineAction(
                operation=RefineOperation.CONSOLIDATE,
                target_memory_ids=[],  # Empty
                reasoning="Test",
                confidence=0.9,
                tenant_id="tenant-123",
                security_domain="development",
            )

    def test_tenant_id_required(self):
        """Test tenant_id is required."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            RefineAction(
                operation=RefineOperation.CONSOLIDATE,
                target_memory_ids=["mem-1"],
                reasoning="Test",
                confidence=0.9,
                tenant_id="",  # Empty
                security_domain="development",
            )

    def test_security_domain_required(self):
        """Test security_domain is required."""
        with pytest.raises(ValueError, match="security_domain is required"):
            RefineAction(
                operation=RefineOperation.CONSOLIDATE,
                target_memory_ids=["mem-1"],
                reasoning="Test",
                confidence=0.9,
                tenant_id="tenant-123",
                security_domain="",  # Empty
            )

    def test_to_dict(self):
        """Test serialization to dictionary."""
        action = RefineAction(
            operation=RefineOperation.PRUNE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Low value",
            confidence=0.85,
            tenant_id="tenant-123",
            security_domain="production",
            agent_id="system",
            action_id="action-001",
            metadata={"auto": True},
        )
        data = action.to_dict()

        assert data["operation"] == "prune"
        assert data["target_memory_ids"] == ["mem-1", "mem-2"]
        assert data["confidence"] == 0.85
        assert data["tenant_id"] == "tenant-123"
        assert data["security_domain"] == "production"
        assert data["agent_id"] == "system"
        assert data["action_id"] == "action-001"
        assert data["metadata"]["auto"] is True
        assert "created_at" in data

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "operation": "consolidate",
            "target_memory_ids": ["mem-1", "mem-2"],
            "reasoning": "Similar memories",
            "confidence": 0.92,
            "tenant_id": "tenant-456",
            "security_domain": "staging",
            "agent_id": "coder-1",
            "action_id": "action-002",
            "metadata": {"source": "auto_discovery"},
            "created_at": "2024-01-15T12:00:00+00:00",
        }
        action = RefineAction.from_dict(data)

        assert action.operation == RefineOperation.CONSOLIDATE
        assert action.target_memory_ids == ["mem-1", "mem-2"]
        assert action.confidence == 0.92
        assert action.tenant_id == "tenant-456"
        assert action.agent_id == "coder-1"


class TestRefineResult:
    """Tests for RefineResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        result = RefineResult(
            success=True,
            operation=RefineOperation.CONSOLIDATE,
            affected_memory_ids=["mem-merged"],
            rollback_token="rollback-123",
            latency_ms=45.5,
        )
        assert result.success is True
        assert result.affected_memory_ids == ["mem-merged"]
        assert result.rollback_token == "rollback-123"
        assert result.error is None

    def test_create_failure_result(self):
        """Test creating a failure result."""
        result = RefineResult(
            success=False,
            operation=RefineOperation.PRUNE,
            affected_memory_ids=[],
            error="Permission denied",
            latency_ms=12.3,
        )
        assert result.success is False
        assert result.affected_memory_ids == []
        assert result.error == "Permission denied"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = RefineResult(
            success=True,
            operation=RefineOperation.CONSOLIDATE,
            affected_memory_ids=["mem-1"],
            action_id="action-001",
            rollback_token="rb-123",
            latency_ms=50.0,
            metrics={"merged_count": 3},
        )
        data = result.to_dict()

        assert data["success"] is True
        assert data["operation"] == "consolidate"
        assert data["affected_memory_ids"] == ["mem-1"]
        assert data["rollback_token"] == "rb-123"
        assert data["latency_ms"] == 50.0
        assert data["metrics"]["merged_count"] == 3


class TestConsolidationCandidate:
    """Tests for ConsolidationCandidate dataclass."""

    def test_create_valid_candidate(self):
        """Test creating a valid consolidation candidate."""
        candidate = ConsolidationCandidate(
            memory_id_a="mem-1",
            memory_id_b="mem-2",
            similarity_score=0.95,
            similarity_metric=SimilarityMetric.COSINE,
        )
        assert candidate.memory_id_a == "mem-1"
        assert candidate.similarity_score == 0.95

    def test_similarity_score_validation(self):
        """Test similarity score must be between 0 and 1."""
        with pytest.raises(ValueError, match="Similarity score must be between"):
            ConsolidationCandidate(
                memory_id_a="mem-1",
                memory_id_b="mem-2",
                similarity_score=1.5,  # Invalid
                similarity_metric=SimilarityMetric.COSINE,
            )

    def test_to_dict(self):
        """Test serialization to dictionary."""
        candidate = ConsolidationCandidate(
            memory_id_a="mem-1",
            memory_id_b="mem-2",
            similarity_score=0.88,
            similarity_metric=SimilarityMetric.SEMANTIC,
            merge_strategy="most_recent",
            overlap_analysis={"shared_tokens": 15},
        )
        data = candidate.to_dict()

        assert data["memory_id_a"] == "mem-1"
        assert data["similarity_score"] == 0.88
        assert data["similarity_metric"] == "semantic"
        assert data["merge_strategy"] == "most_recent"


class TestPruneCandidate:
    """Tests for PruneCandidate dataclass."""

    def test_create_valid_candidate(self):
        """Test creating a valid prune candidate."""
        candidate = PruneCandidate(
            memory_id="mem-old",
            prune_score=0.85,
            access_count=0,
            value_score=0.1,
            age_days=45,
            reasons=["Never accessed", "Low value"],
        )
        assert candidate.memory_id == "mem-old"
        assert candidate.prune_score == 0.85
        assert len(candidate.reasons) == 2

    def test_prune_score_validation(self):
        """Test prune score must be between 0 and 1."""
        with pytest.raises(ValueError, match="Prune score must be between"):
            PruneCandidate(
                memory_id="mem-1",
                prune_score=1.2,  # Invalid
            )

    def test_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime.now(timezone.utc)
        candidate = PruneCandidate(
            memory_id="mem-old",
            prune_score=0.9,
            last_accessed=now,
            access_count=1,
            value_score=0.15,
            age_days=60,
            reasons=["Stale"],
        )
        data = candidate.to_dict()

        assert data["memory_id"] == "mem-old"
        assert data["prune_score"] == 0.9
        assert data["last_accessed"] is not None


class TestEvolutionRecord:
    """Tests for EvolutionRecord dataclass."""

    def test_to_dynamo_item(self):
        """Test conversion to DynamoDB item format."""
        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )
        result = RefineResult(
            success=True,
            operation=RefineOperation.CONSOLIDATE,
            affected_memory_ids=["mem-merged"],
        )
        record = EvolutionRecord(
            record_id="rec-001",
            operation=RefineOperation.CONSOLIDATE,
            agent_id="coder-1",
            tenant_id="tenant-123",
            security_domain="development",
            action=action,
            result=result,
            task_id="task-456",
            task_sequence_number=5,
        )

        item = record.to_dynamo_item()

        # Verify composite partition key
        assert "#" in item["pk"]  # Format: agent_id#YYYY-MM-DD
        assert item["pk"].startswith("coder-1#")
        assert item["agent_id"] == "coder-1"
        assert item["tenant_id"] == "tenant-123"
        assert item["task_sequence_number"] == 5
        assert item["outcome"] == "success"


class TestMemorySnapshot:
    """Tests for MemorySnapshot dataclass."""

    def test_create_snapshot(self):
        """Test creating a memory snapshot."""
        snapshot = MemorySnapshot(
            snapshot_id="snap-001",
            memory_ids=["mem-1", "mem-2"],
            snapshot_data={"memories": [{"id": "mem-1"}]},
            tenant_id="tenant-123",
            security_domain="development",
        )
        assert snapshot.snapshot_id == "snap-001"
        assert len(snapshot.memory_ids) == 2

    def test_to_dict(self):
        """Test serialization to dictionary."""
        snapshot = MemorySnapshot(
            snapshot_id="snap-002",
            memory_ids=["mem-1"],
            snapshot_data={"state": "before_prune"},
            tenant_id="tenant-456",
            security_domain="staging",
        )
        data = snapshot.to_dict()

        assert data["snapshot_id"] == "snap-002"
        assert data["memory_ids"] == ["mem-1"]
        assert data["tenant_id"] == "tenant-456"
