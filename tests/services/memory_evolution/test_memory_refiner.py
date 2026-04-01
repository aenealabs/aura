"""Tests for memory refiner service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.memory_evolution import (
    CircuitBreakerOpen,
    ConsolidationError,
    FeatureDisabledError,
    MemoryEvolutionConfig,
    MemoryRefiner,
    PruneError,
    RefineAction,
    RefineOperation,
    SecurityBoundaryViolation,
    ValidationError,
)


class TestMemoryRefiner:
    """Tests for MemoryRefiner service."""

    @pytest.mark.asyncio
    async def test_consolidate_success(
        self,
        memory_refiner: MemoryRefiner,
        consolidate_action: RefineAction,
    ):
        """Test successful consolidation operation."""
        result = await memory_refiner.refine(consolidate_action)

        assert result.success is True
        assert result.operation == RefineOperation.CONSOLIDATE
        assert len(result.affected_memory_ids) == 1
        assert result.affected_memory_ids[0] == "mem-merged"
        assert result.rollback_token is not None
        assert result.latency_ms > 0
        assert result.metrics["merged_count"] == 2

    @pytest.mark.asyncio
    async def test_consolidate_requires_minimum_memories(
        self,
        memory_refiner: MemoryRefiner,
        mock_memory_store: MagicMock,
    ):
        """Test consolidation requires at least 2 memories."""
        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1"],  # Only 1
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        # Mock returning exactly the requested memories for security validation
        mock_memory_store.get_memories = AsyncMock(
            return_value=[{"memory_id": "mem-1"}]
        )

        with pytest.raises(ConsolidationError, match="at least 2 memory IDs"):
            await memory_refiner.refine(action)

    @pytest.mark.asyncio
    async def test_consolidate_respects_batch_size_limit(
        self,
        memory_refiner: MemoryRefiner,
        mock_memory_store: MagicMock,
    ):
        """Test consolidation respects max batch size."""
        # Create action with too many memories
        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=[f"mem-{i}" for i in range(20)],  # 20 > max 10
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        # Mock returning all memories as accessible
        mock_memory_store.get_memories = AsyncMock(
            return_value=[{"memory_id": f"mem-{i}"} for i in range(20)]
        )

        with pytest.raises(ConsolidationError, match="batch size exceeds maximum"):
            await memory_refiner.refine(action)

    @pytest.mark.asyncio
    async def test_consolidate_validates_confidence(
        self,
        memory_refiner: MemoryRefiner,
    ):
        """Test consolidation validates confidence threshold."""
        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.5,  # Below default 0.7 threshold
            tenant_id="tenant-123",
            security_domain="development",
        )

        with pytest.raises(ValidationError, match="Confidence.*below minimum"):
            await memory_refiner.refine(action)

    @pytest.mark.asyncio
    async def test_prune_success(
        self,
        memory_refiner: MemoryRefiner,
        prune_action: RefineAction,
        mock_memory_store: MagicMock,
    ):
        """Test successful prune operation."""
        # Mock getting memories for validation
        mock_memory_store.get_memories = AsyncMock(
            return_value=[
                {"memory_id": "mem-old-1"},
                {"memory_id": "mem-old-2"},
            ]
        )

        result = await memory_refiner.refine(prune_action)

        assert result.success is True
        assert result.operation == RefineOperation.PRUNE
        assert len(result.affected_memory_ids) == 2
        assert result.rollback_token is not None
        assert result.metrics["requested_count"] == 2
        assert result.metrics["pruned_count"] == 2

    @pytest.mark.asyncio
    async def test_prune_respects_batch_size_limit(
        self,
        memory_refiner: MemoryRefiner,
        mock_memory_store: MagicMock,
    ):
        """Test prune respects max batch size."""
        # Create action with too many memories
        action = RefineAction(
            operation=RefineOperation.PRUNE,
            target_memory_ids=[f"mem-{i}" for i in range(60)],  # 60 > max 50
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        # Mock returning all memories as accessible
        mock_memory_store.get_memories = AsyncMock(
            return_value=[{"memory_id": f"mem-{i}"} for i in range(60)]
        )

        with pytest.raises(PruneError, match="batch size exceeds maximum"):
            await memory_refiner.refine(action)

    @pytest.mark.asyncio
    async def test_prune_partial_success(
        self,
        memory_refiner: MemoryRefiner,
        mock_memory_store: MagicMock,
    ):
        """Test prune reports partial success when some deletions fail."""
        action = RefineAction(
            operation=RefineOperation.PRUNE,
            target_memory_ids=["mem-1", "mem-2", "mem-3"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        # Mock get_memories to return all
        mock_memory_store.get_memories = AsyncMock(
            return_value=[
                {"memory_id": "mem-1"},
                {"memory_id": "mem-2"},
                {"memory_id": "mem-3"},
            ]
        )

        # Mock soft_delete to fail for one memory
        call_count = [0]

        async def mock_soft_delete(memory_id: str, tenant_id: str, reason: str):
            call_count[0] += 1
            return memory_id != "mem-2"  # Fail for mem-2

        mock_memory_store.soft_delete_memory = mock_soft_delete

        result = await memory_refiner.refine(action)

        assert result.success is True
        assert result.metrics["requested_count"] == 3
        assert result.metrics["pruned_count"] == 2
        assert "mem-1" in result.affected_memory_ids
        assert "mem-2" not in result.affected_memory_ids
        assert "mem-3" in result.affected_memory_ids


class TestSecurityEnforcement:
    """Tests for security constraint enforcement."""

    @pytest.mark.asyncio
    async def test_requires_tenant_id(
        self,
        memory_refiner: MemoryRefiner,
    ):
        """Test operations require tenant_id."""
        # This should fail at RefineAction creation due to validation
        with pytest.raises(ValueError, match="tenant_id is required"):
            RefineAction(
                operation=RefineOperation.CONSOLIDATE,
                target_memory_ids=["mem-1", "mem-2"],
                reasoning="Test",
                confidence=0.9,
                tenant_id="",  # Empty
                security_domain="development",
            )

    @pytest.mark.asyncio
    async def test_requires_security_domain(
        self,
        memory_refiner: MemoryRefiner,
    ):
        """Test operations require security_domain."""
        # This should fail at RefineAction creation due to validation
        with pytest.raises(ValueError, match="security_domain is required"):
            RefineAction(
                operation=RefineOperation.CONSOLIDATE,
                target_memory_ids=["mem-1", "mem-2"],
                reasoning="Test",
                confidence=0.9,
                tenant_id="tenant-123",
                security_domain="",  # Empty
            )

    @pytest.mark.asyncio
    async def test_validates_memory_access(
        self,
        memory_refiner: MemoryRefiner,
        mock_memory_store: MagicMock,
    ):
        """Test validates that target memories are accessible."""
        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2", "mem-inaccessible"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        # Mock returning only 2 of 3 memories (mem-inaccessible not found)
        mock_memory_store.get_memories = AsyncMock(
            return_value=[
                {"memory_id": "mem-1"},
                {"memory_id": "mem-2"},
                # mem-inaccessible not returned
            ]
        )

        with pytest.raises(SecurityBoundaryViolation, match="Cannot access memories"):
            await memory_refiner.refine(action)


class TestFeatureFlags:
    """Tests for feature flag enforcement."""

    @pytest.mark.asyncio
    async def test_reinforce_disabled_by_default(
        self,
        memory_refiner: MemoryRefiner,
    ):
        """Test REINFORCE operation is disabled by default."""
        action = RefineAction(
            operation=RefineOperation.REINFORCE,
            target_memory_ids=["mem-1"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        with pytest.raises(FeatureDisabledError) as exc_info:
            await memory_refiner.refine(action)

        assert "reinforce" in str(exc_info.value).lower()
        assert exc_info.value.phase == "1b"

    @pytest.mark.asyncio
    async def test_abstract_disabled_by_default(
        self,
        memory_refiner: MemoryRefiner,
    ):
        """Test ABSTRACT operation is disabled by default."""
        action = RefineAction(
            operation=RefineOperation.ABSTRACT,
            target_memory_ids=["mem-1"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        with pytest.raises(FeatureDisabledError) as exc_info:
            await memory_refiner.refine(action)

        assert "abstract" in str(exc_info.value).lower()
        assert exc_info.value.phase == "3"

    @pytest.mark.asyncio
    async def test_link_disabled_by_default(
        self,
        memory_refiner: MemoryRefiner,
    ):
        """Test LINK operation is disabled by default."""
        action = RefineAction(
            operation=RefineOperation.LINK,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        with pytest.raises(FeatureDisabledError) as exc_info:
            await memory_refiner.refine(action)

        assert "link" in str(exc_info.value).lower()
        assert exc_info.value.phase == "5"


class TestCircuitBreaker:
    """Tests for circuit breaker behavior."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(
        self,
        mock_memory_store: MagicMock,
        mock_record_store: MagicMock,
        test_config: MemoryEvolutionConfig,
    ):
        """Test circuit breaker opens after 3 consecutive failures."""
        # Create refiner without metrics publisher
        refiner = MemoryRefiner(
            memory_store=mock_memory_store,
            record_store=mock_record_store,
            config=test_config,
        )

        # Mock merge to fail
        mock_memory_store.merge_memories = AsyncMock(
            side_effect=Exception("Merge failed")
        )

        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        # Fail 3 times
        for _ in range(3):
            with pytest.raises(Exception, match="Merge failed"):
                await refiner.refine(action)

        # 4th attempt should hit circuit breaker
        with pytest.raises(CircuitBreakerOpen) as exc_info:
            await refiner.refine(action)

        assert exc_info.value.failure_count >= 3
        assert exc_info.value.cooldown_remaining_seconds > 0

    @pytest.mark.asyncio
    async def test_circuit_resets_on_success(
        self,
        memory_refiner: MemoryRefiner,
        consolidate_action: RefineAction,
    ):
        """Test circuit breaker resets on successful operation."""
        # Run successful operations
        for _ in range(5):
            result = await memory_refiner.refine(consolidate_action)
            assert result.success is True

        # Circuit breaker should not be triggered


class TestDiscoveryMethods:
    """Tests for consolidation and prune candidate discovery."""

    @pytest.mark.asyncio
    async def test_find_consolidation_candidates(
        self,
        memory_refiner: MemoryRefiner,
        mock_memory_store: MagicMock,
    ):
        """Test finding consolidation candidates."""
        candidates = await memory_refiner.find_consolidation_candidates(
            tenant_id="tenant-123",
            security_domain="development",
        )

        assert len(candidates) == 2
        assert candidates[0].memory_id_a == "mem-1"
        assert candidates[0].memory_id_b == "mem-2"
        assert candidates[0].similarity_score == 0.95

    @pytest.mark.asyncio
    async def test_find_consolidation_candidates_disabled(
        self,
        memory_refiner: MemoryRefiner,
        mock_memory_store: MagicMock,
    ):
        """Test discovery returns empty when disabled."""
        memory_refiner.config.consolidation.auto_discovery_enabled = False

        candidates = await memory_refiner.find_consolidation_candidates(
            tenant_id="tenant-123",
            security_domain="development",
        )

        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_find_prune_candidates(
        self,
        memory_refiner: MemoryRefiner,
        mock_memory_store: MagicMock,
    ):
        """Test finding prune candidates."""
        candidates = await memory_refiner.find_prune_candidates(
            tenant_id="tenant-123",
            security_domain="development",
        )

        # Should find candidates based on mock data
        assert len(candidates) > 0
        for candidate in candidates:
            assert candidate.prune_score >= 0.8

    @pytest.mark.asyncio
    async def test_find_prune_candidates_respects_access_protection(
        self,
        memory_refiner: MemoryRefiner,
        mock_memory_store: MagicMock,
    ):
        """Test prune discovery respects minimum access protection."""
        # Mock memories with high access counts
        mock_memory_store.get_prune_candidates = AsyncMock(
            return_value=[
                {
                    "memory_id": "mem-protected",
                    "access_count": 10,  # Above min_access_protection (3)
                    "value_score": 0.1,
                    "age_days": 100,
                },
            ]
        )

        candidates = await memory_refiner.find_prune_candidates(
            tenant_id="tenant-123",
            security_domain="development",
        )

        # High access count should protect from pruning
        assert len(candidates) == 0


class TestMetricsPublishing:
    """Tests for metrics publishing."""

    @pytest.mark.asyncio
    async def test_publishes_success_metrics(
        self,
        memory_refiner: MemoryRefiner,
        consolidate_action: RefineAction,
        mock_metrics_publisher: MagicMock,
    ):
        """Test metrics are published on success."""
        await memory_refiner.refine(consolidate_action)

        mock_metrics_publisher.publish_refine_result.assert_called_once()
        call_args = mock_metrics_publisher.publish_refine_result.call_args
        assert call_args[0][0] == RefineOperation.CONSOLIDATE  # operation
        assert call_args[0][1] is True  # success
        assert call_args[0][2] > 0  # latency_ms

    @pytest.mark.asyncio
    async def test_publishes_failure_metrics(
        self,
        mock_memory_store: MagicMock,
        mock_record_store: MagicMock,
        mock_metrics_publisher: MagicMock,
        test_config: MemoryEvolutionConfig,
    ):
        """Test metrics are published on failure."""
        refiner = MemoryRefiner(
            memory_store=mock_memory_store,
            record_store=mock_record_store,
            metrics_publisher=mock_metrics_publisher,
            config=test_config,
        )

        # Mock merge to fail
        mock_memory_store.merge_memories = AsyncMock(
            side_effect=Exception("Merge failed")
        )

        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        with pytest.raises(Exception):
            await refiner.refine(action)

        mock_metrics_publisher.publish_refine_result.assert_called_once()
        call_args = mock_metrics_publisher.publish_refine_result.call_args
        assert call_args[0][1] is False  # success = False


class TestEvolutionRecordStorage:
    """Tests for evolution record storage."""

    @pytest.mark.asyncio
    async def test_saves_evolution_record_on_success(
        self,
        memory_refiner: MemoryRefiner,
        consolidate_action: RefineAction,
        mock_record_store: MagicMock,
    ):
        """Test evolution record is saved on success."""
        await memory_refiner.refine(consolidate_action)

        mock_record_store.save_record.assert_called_once()
        saved_record = mock_record_store.save_record.call_args[0][0]
        assert saved_record.operation == RefineOperation.CONSOLIDATE
        assert saved_record.tenant_id == "tenant-123"

    @pytest.mark.asyncio
    async def test_saves_evolution_record_on_failure(
        self,
        mock_memory_store: MagicMock,
        mock_record_store: MagicMock,
        test_config: MemoryEvolutionConfig,
    ):
        """Test evolution record is saved even on failure."""
        refiner = MemoryRefiner(
            memory_store=mock_memory_store,
            record_store=mock_record_store,
            config=test_config,
        )

        # Mock merge to fail
        mock_memory_store.merge_memories = AsyncMock(
            side_effect=Exception("Merge failed")
        )

        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        with pytest.raises(Exception):
            await refiner.refine(action)

        mock_record_store.save_record.assert_called_once()
        saved_record = mock_record_store.save_record.call_args[0][0]
        assert saved_record.result.success is False


class TestPruneScoreCalculation:
    """Tests for prune score calculation."""

    def test_calculate_prune_score_never_accessed(
        self,
        memory_refiner: MemoryRefiner,
    ):
        """Test high prune score for never accessed memories."""
        score = memory_refiner._calculate_prune_score(
            access_count=0,
            value_score=0.1,
            age_days=30,
        )
        # Should be high since never accessed and low value
        assert score > 0.7

    def test_calculate_prune_score_frequently_accessed(
        self,
        memory_refiner: MemoryRefiner,
    ):
        """Test low prune score for frequently accessed memories."""
        score = memory_refiner._calculate_prune_score(
            access_count=10,
            value_score=0.8,
            age_days=10,
        )
        # Should be low since frequently accessed and high value
        assert score < 0.3

    def test_calculate_prune_score_bounded(
        self,
        memory_refiner: MemoryRefiner,
    ):
        """Test prune score is always between 0 and 1."""
        # Test extreme values
        score_low = memory_refiner._calculate_prune_score(
            access_count=100,
            value_score=1.0,
            age_days=0,
        )
        score_high = memory_refiner._calculate_prune_score(
            access_count=0,
            value_score=0.0,
            age_days=365,
        )

        assert 0.0 <= score_low <= 1.0
        assert 0.0 <= score_high <= 1.0
