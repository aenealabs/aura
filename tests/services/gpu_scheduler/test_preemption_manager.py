"""Tests for GPU Preemption Manager.

Tests job preemption logic and checkpoint coordination per ADR-061 Phase 2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.gpu_scheduler.exceptions import PreemptionError
from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJob,
    GPUJobPriority,
    GPUJobStatus,
    GPUJobType,
    PreemptionReason,
)
from src.services.gpu_scheduler.preemption_manager import (
    CHECKPOINT_TIMEOUT_SECONDS,
    PreemptionManager,
    get_preemption_manager,
    init_preemption_manager,
)


@pytest.fixture
def mock_k8s_client():
    """Create mock Kubernetes client for preemption tests."""
    client = MagicMock()
    client.signal_checkpoint = AsyncMock(return_value=True)
    client.check_checkpoint_marker = AsyncMock(return_value=True)
    client.delete_job = AsyncMock(return_value=True)
    return client


@pytest.fixture
def preemption_manager(mock_k8s_client):
    """Create preemption manager with mocked K8s client."""
    return PreemptionManager(
        k8s_client=mock_k8s_client,
        checkpoint_timeout_seconds=5,  # Short timeout for tests
    )


@pytest.fixture
def high_priority_job(sample_embedding_config: EmbeddingJobConfig) -> GPUJob:
    """Create a HIGH priority job."""
    return GPUJob(
        job_id="job-high-123",
        organization_id="org-test",
        user_id="user-test",
        job_type=GPUJobType.EMBEDDING_GENERATION,
        status=GPUJobStatus.QUEUED,
        priority=GPUJobPriority.HIGH,
        config=sample_embedding_config,
        gpu_memory_gb=8,
        max_runtime_hours=2,
        checkpoint_enabled=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def low_priority_job(sample_embedding_config: EmbeddingJobConfig) -> GPUJob:
    """Create a LOW priority running job."""
    return GPUJob(
        job_id="job-low-456",
        organization_id="org-test",
        user_id="user-test",
        job_type=GPUJobType.EMBEDDING_GENERATION,
        status=GPUJobStatus.RUNNING,
        priority=GPUJobPriority.LOW,
        config=sample_embedding_config,
        gpu_memory_gb=8,
        max_runtime_hours=2,
        checkpoint_enabled=True,
        checkpoint_s3_path="s3://checkpoints/org-test/job-low-456/",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def normal_priority_job(sample_embedding_config: EmbeddingJobConfig) -> GPUJob:
    """Create a NORMAL priority running job."""
    return GPUJob(
        job_id="job-normal-789",
        organization_id="org-test",
        user_id="user-test",
        job_type=GPUJobType.EMBEDDING_GENERATION,
        status=GPUJobStatus.RUNNING,
        priority=GPUJobPriority.NORMAL,
        config=sample_embedding_config,
        gpu_memory_gb=8,
        max_runtime_hours=2,
        checkpoint_enabled=True,
        checkpoint_s3_path="s3://checkpoints/org-test/job-normal-789/",
        created_at=datetime.now(timezone.utc),
    )


class TestPreemptionValidation:
    """Tests for preemption validation rules."""

    def test_high_can_preempt_low(self, preemption_manager: PreemptionManager):
        """Test that HIGH priority can preempt LOW priority."""
        result = preemption_manager._can_preempt(
            GPUJobPriority.HIGH, GPUJobPriority.LOW
        )
        assert result is True

    def test_high_cannot_preempt_normal(self, preemption_manager: PreemptionManager):
        """Test that HIGH priority cannot preempt NORMAL priority."""
        result = preemption_manager._can_preempt(
            GPUJobPriority.HIGH, GPUJobPriority.NORMAL
        )
        assert result is False

    def test_high_cannot_preempt_high(self, preemption_manager: PreemptionManager):
        """Test that HIGH priority cannot preempt HIGH priority."""
        result = preemption_manager._can_preempt(
            GPUJobPriority.HIGH, GPUJobPriority.HIGH
        )
        assert result is False

    def test_normal_cannot_preempt_low(self, preemption_manager: PreemptionManager):
        """Test that NORMAL priority cannot preempt LOW priority."""
        result = preemption_manager._can_preempt(
            GPUJobPriority.NORMAL, GPUJobPriority.LOW
        )
        assert result is False

    def test_normal_cannot_preempt_normal(self, preemption_manager: PreemptionManager):
        """Test that NORMAL priority cannot preempt NORMAL priority."""
        result = preemption_manager._can_preempt(
            GPUJobPriority.NORMAL, GPUJobPriority.NORMAL
        )
        assert result is False

    def test_low_cannot_preempt_anything(self, preemption_manager: PreemptionManager):
        """Test that LOW priority cannot preempt any priority."""
        for target in GPUJobPriority:
            result = preemption_manager._can_preempt(GPUJobPriority.LOW, target)
            assert result is False


class TestPriorityBoost:
    """Tests for priority boost calculation."""

    def test_low_boosted_to_normal(self, preemption_manager: PreemptionManager):
        """Test that LOW priority is boosted to NORMAL after preemption."""
        job = MagicMock()
        job.priority = GPUJobPriority.LOW

        new_priority = preemption_manager._calculate_priority_boost(job)
        assert new_priority == GPUJobPriority.NORMAL

    def test_normal_stays_normal(self, preemption_manager: PreemptionManager):
        """Test that NORMAL priority stays NORMAL after preemption."""
        job = MagicMock()
        job.priority = GPUJobPriority.NORMAL

        new_priority = preemption_manager._calculate_priority_boost(job)
        assert new_priority == GPUJobPriority.NORMAL

    def test_priority_boost_disabled(self, mock_k8s_client):
        """Test priority boost can be disabled."""
        manager = PreemptionManager(
            k8s_client=mock_k8s_client,
            priority_boost_on_preemption=False,
        )

        job = MagicMock()
        job.priority = GPUJobPriority.LOW

        new_priority = manager._calculate_priority_boost(job)
        assert new_priority == GPUJobPriority.LOW


class TestPreemptJob:
    """Tests for the preempt_job method."""

    @pytest.mark.asyncio
    async def test_successful_preemption(
        self,
        preemption_manager: PreemptionManager,
        high_priority_job: GPUJob,
        low_priority_job: GPUJob,
    ):
        """Test successful job preemption."""
        event = await preemption_manager.preempt_job(
            preempting_job=high_priority_job,
            preempted_job=low_priority_job,
        )

        assert event.preempted_job_id == low_priority_job.job_id
        assert event.preempting_job_id == high_priority_job.job_id
        assert event.reason == PreemptionReason.HIGH_PRIORITY_JOB
        assert event.checkpoint_saved is True
        assert event.re_queued is True
        assert event.priority_boost_applied is True
        assert event.original_priority == GPUJobPriority.LOW
        assert event.new_priority == GPUJobPriority.NORMAL

    @pytest.mark.asyncio
    async def test_preemption_calls_k8s_methods(
        self,
        preemption_manager: PreemptionManager,
        high_priority_job: GPUJob,
        low_priority_job: GPUJob,
        mock_k8s_client,
    ):
        """Test that preemption calls correct K8s methods."""
        await preemption_manager.preempt_job(
            preempting_job=high_priority_job,
            preempted_job=low_priority_job,
        )

        mock_k8s_client.signal_checkpoint.assert_called_once_with(
            low_priority_job.job_id
        )
        mock_k8s_client.check_checkpoint_marker.assert_called()
        mock_k8s_client.delete_job.assert_called_once_with(low_priority_job.job_id)

    @pytest.mark.asyncio
    async def test_preemption_invalid_priorities_raises_error(
        self,
        preemption_manager: PreemptionManager,
        high_priority_job: GPUJob,
        normal_priority_job: GPUJob,
    ):
        """Test that invalid preemption raises PreemptionError."""
        with pytest.raises(PreemptionError) as exc_info:
            await preemption_manager.preempt_job(
                preempting_job=high_priority_job,
                preempted_job=normal_priority_job,
            )

        assert "Cannot preempt normal priority job" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_preemption_without_checkpoint(
        self,
        preemption_manager: PreemptionManager,
        high_priority_job: GPUJob,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test preemption when checkpointing is disabled."""
        low_job_no_checkpoint = GPUJob(
            job_id="job-low-no-cp",
            organization_id="org-test",
            user_id="user-test",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.LOW,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=False,
            created_at=datetime.now(timezone.utc),
        )

        event = await preemption_manager.preempt_job(
            preempting_job=high_priority_job,
            preempted_job=low_job_no_checkpoint,
        )

        assert event.checkpoint_saved is False
        assert event.checkpoint_s3_path is None

    @pytest.mark.asyncio
    async def test_preemption_checkpoint_timeout(
        self,
        mock_k8s_client,
        high_priority_job: GPUJob,
        low_priority_job: GPUJob,
    ):
        """Test preemption continues after checkpoint timeout."""
        # Make checkpoint marker never appear
        mock_k8s_client.check_checkpoint_marker = AsyncMock(return_value=False)

        manager = PreemptionManager(
            k8s_client=mock_k8s_client,
            checkpoint_timeout_seconds=1,  # Very short timeout
        )

        event = await manager.preempt_job(
            preempting_job=high_priority_job,
            preempted_job=low_priority_job,
        )

        # Preemption should complete even without checkpoint
        assert event.checkpoint_saved is False
        mock_k8s_client.delete_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_preemption_k8s_delete_fails(
        self,
        mock_k8s_client,
        high_priority_job: GPUJob,
        low_priority_job: GPUJob,
    ):
        """Test that K8s delete failure raises PreemptionError."""
        mock_k8s_client.delete_job = AsyncMock(side_effect=Exception("K8s error"))

        manager = PreemptionManager(
            k8s_client=mock_k8s_client,
            checkpoint_timeout_seconds=1,
        )

        with pytest.raises(PreemptionError) as exc_info:
            await manager.preempt_job(
                preempting_job=high_priority_job,
                preempted_job=low_priority_job,
            )

        assert "Failed to terminate K8s job" in str(exc_info.value)


class TestSpotInterruption:
    """Tests for Spot instance interruption handling."""

    @pytest.mark.asyncio
    async def test_spot_interruption_handling(
        self,
        preemption_manager: PreemptionManager,
        low_priority_job: GPUJob,
    ):
        """Test handling Spot interruption."""
        event = await preemption_manager.handle_spot_interruption(low_priority_job)

        assert event.preempted_job_id == low_priority_job.job_id
        assert event.preempting_job_id == "spot_interruption"
        assert event.reason == PreemptionReason.SPOT_INTERRUPTION
        assert event.re_queued is True
        assert event.priority_boost_applied is True
        assert event.new_priority == GPUJobPriority.HIGH

    @pytest.mark.asyncio
    async def test_spot_interruption_checkpoint(
        self,
        preemption_manager: PreemptionManager,
        low_priority_job: GPUJob,
        mock_k8s_client,
    ):
        """Test checkpoint is attempted during Spot interruption."""
        event = await preemption_manager.handle_spot_interruption(low_priority_job)

        assert event.checkpoint_saved is True
        mock_k8s_client.signal_checkpoint.assert_called()

    @pytest.mark.asyncio
    async def test_spot_interruption_boosts_all_priorities_to_high(
        self,
        preemption_manager: PreemptionManager,
        normal_priority_job: GPUJob,
    ):
        """Test that Spot interruption boosts all jobs to HIGH."""
        event = await preemption_manager.handle_spot_interruption(normal_priority_job)

        assert event.original_priority == GPUJobPriority.NORMAL
        assert event.new_priority == GPUJobPriority.HIGH


class TestCheckpointPolling:
    """Tests for checkpoint marker polling."""

    @pytest.mark.asyncio
    async def test_checkpoint_polling_success(
        self,
        mock_k8s_client,
        low_priority_job: GPUJob,
    ):
        """Test successful checkpoint marker detection."""
        # Return True immediately on first check
        mock_k8s_client.check_checkpoint_marker = AsyncMock(return_value=True)

        # Use a longer timeout to allow for polling
        manager = PreemptionManager(
            k8s_client=mock_k8s_client,
            checkpoint_timeout_seconds=10,
        )

        result = await manager._signal_and_wait_checkpoint(low_priority_job)
        assert result is True

    @pytest.mark.asyncio
    async def test_checkpoint_no_s3_path(
        self,
        preemption_manager: PreemptionManager,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test checkpoint polling with no S3 path."""
        job_no_path = GPUJob(
            job_id="job-no-path",
            organization_id="org-test",
            user_id="user-test",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.LOW,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            checkpoint_s3_path=None,
            created_at=datetime.now(timezone.utc),
        )

        result = await preemption_manager._poll_checkpoint_marker(job_no_path)
        assert result is False


class TestPreemptionReasons:
    """Tests for preemption reason handling."""

    @pytest.mark.asyncio
    async def test_high_priority_reason(
        self,
        preemption_manager: PreemptionManager,
        high_priority_job: GPUJob,
        low_priority_job: GPUJob,
    ):
        """Test HIGH_PRIORITY_JOB reason."""
        event = await preemption_manager.preempt_job(
            preempting_job=high_priority_job,
            preempted_job=low_priority_job,
            reason=PreemptionReason.HIGH_PRIORITY_JOB,
        )

        assert event.reason == PreemptionReason.HIGH_PRIORITY_JOB

    @pytest.mark.asyncio
    async def test_quota_enforcement_reason(
        self,
        preemption_manager: PreemptionManager,
        high_priority_job: GPUJob,
        low_priority_job: GPUJob,
    ):
        """Test QUOTA_ENFORCEMENT reason."""
        event = await preemption_manager.preempt_job(
            preempting_job=high_priority_job,
            preempted_job=low_priority_job,
            reason=PreemptionReason.QUOTA_ENFORCEMENT,
        )

        assert event.reason == PreemptionReason.QUOTA_ENFORCEMENT


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_preemption_manager_returns_same_instance(self):
        """Test singleton returns same instance."""
        # Reset singleton
        import src.services.gpu_scheduler.preemption_manager as pm_module

        pm_module._preemption_manager = None

        manager1 = get_preemption_manager()
        manager2 = get_preemption_manager()

        assert manager1 is manager2

    def test_init_preemption_manager(self, mock_k8s_client):
        """Test initializing preemption manager with dependencies."""
        # Reset singleton
        import src.services.gpu_scheduler.preemption_manager as pm_module

        pm_module._preemption_manager = None

        manager = init_preemption_manager(
            k8s_client=mock_k8s_client,
            s3_client=MagicMock(),
        )

        assert manager.k8s_client is mock_k8s_client
        assert get_preemption_manager() is manager


class TestConstants:
    """Tests for module constants."""

    def test_checkpoint_timeout_default(self):
        """Test default checkpoint timeout is 5 minutes."""
        assert CHECKPOINT_TIMEOUT_SECONDS == 300
