"""Tests for GPU Scheduler models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJob,
    GPUJobCreateRequest,
    GPUJobErrorType,
    GPUJobPriority,
    GPUJobStatus,
    GPUJobType,
    GPUQuota,
    GPUResourceStatus,
    LocalInferenceConfig,
    MemoryConsolidationConfig,
    SWERLTrainingConfig,
    VulnerabilityTrainingConfig,
)


class TestGPUJobType:
    """Tests for GPUJobType enum."""

    def test_job_types(self):
        """Test all job types are defined."""
        assert GPUJobType.EMBEDDING_GENERATION.value == "embedding_generation"
        assert GPUJobType.LOCAL_INFERENCE.value == "local_inference"
        assert GPUJobType.VULNERABILITY_TRAINING.value == "vulnerability_training"
        assert GPUJobType.SWE_RL_TRAINING.value == "swe_rl_training"
        assert GPUJobType.MEMORY_CONSOLIDATION.value == "memory_consolidation"


class TestGPUJobStatus:
    """Tests for GPUJobStatus enum."""

    def test_job_statuses(self):
        """Test all job statuses are defined."""
        assert GPUJobStatus.QUEUED.value == "queued"
        assert GPUJobStatus.STARTING.value == "starting"
        assert GPUJobStatus.RUNNING.value == "running"
        assert GPUJobStatus.COMPLETED.value == "completed"
        assert GPUJobStatus.FAILED.value == "failed"
        assert GPUJobStatus.CANCELLED.value == "cancelled"


class TestEmbeddingJobConfig:
    """Tests for EmbeddingJobConfig model."""

    def test_valid_config(self):
        """Test valid embedding config."""
        config = EmbeddingJobConfig(
            repository_id="test-repo",
            branch="main",
            model="codebert-base",
        )
        assert config.repository_id == "test-repo"
        assert config.branch == "main"
        assert config.model == "codebert-base"
        assert config.batch_size == 32  # default

    def test_invalid_repository_id(self):
        """Test invalid repository ID format."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingJobConfig(
                repository_id="invalid repo!@#",
                branch="main",
            )
        assert "Invalid repository ID format" in str(exc_info.value)

    def test_invalid_branch(self):
        """Test invalid branch name format."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingJobConfig(
                repository_id="test-repo",
                branch="invalid branch name!",
            )
        assert "Invalid branch name format" in str(exc_info.value)

    def test_invalid_model(self):
        """Test invalid model name."""
        with pytest.raises(ValidationError):
            EmbeddingJobConfig(
                repository_id="test-repo",
                branch="main",
                model="invalid-model",
            )

    def test_batch_size_bounds(self):
        """Test batch size validation."""
        # Valid batch size
        config = EmbeddingJobConfig(
            repository_id="test-repo",
            batch_size=64,
        )
        assert config.batch_size == 64

        # Invalid batch size (too low)
        with pytest.raises(ValidationError):
            EmbeddingJobConfig(
                repository_id="test-repo",
                batch_size=0,
            )

        # Invalid batch size (too high)
        with pytest.raises(ValidationError):
            EmbeddingJobConfig(
                repository_id="test-repo",
                batch_size=256,
            )


class TestVulnerabilityTrainingConfig:
    """Tests for VulnerabilityTrainingConfig model."""

    def test_valid_config(self):
        """Test valid vulnerability training config."""
        config = VulnerabilityTrainingConfig(
            dataset_id="dataset-123",
            epochs=20,
            batch_size=64,
            learning_rate=0.001,
        )
        assert config.dataset_id == "dataset-123"
        assert config.epochs == 20
        assert config.batch_size == 64
        assert config.learning_rate == 0.001

    def test_learning_rate_bounds(self):
        """Test learning rate validation."""
        with pytest.raises(ValidationError):
            VulnerabilityTrainingConfig(
                dataset_id="dataset-123",
                learning_rate=0.5,  # Too high
            )


class TestSWERLTrainingConfig:
    """Tests for SWERLTrainingConfig model."""

    def test_valid_config(self):
        """Test valid SWE-RL training config."""
        config = SWERLTrainingConfig(
            batch_id="batch-123",
            max_epochs=200,
            checkpoint_interval_minutes=30,
        )
        assert config.batch_id == "batch-123"
        assert config.max_epochs == 200
        assert config.checkpoint_interval_minutes == 30

    def test_checkpoint_interval_bounds(self):
        """Test checkpoint interval validation."""
        with pytest.raises(ValidationError):
            SWERLTrainingConfig(
                batch_id="batch-123",
                checkpoint_interval_minutes=2,  # Too low
            )


class TestMemoryConsolidationConfig:
    """Tests for MemoryConsolidationConfig model."""

    def test_valid_config(self):
        """Test valid memory consolidation config."""
        config = MemoryConsolidationConfig(
            session_id="session-123",
            retention_threshold=0.8,
            consolidation_strategy="incremental",
        )
        assert config.session_id == "session-123"
        assert config.retention_threshold == 0.8
        assert config.consolidation_strategy == "incremental"

    def test_retention_threshold_bounds(self):
        """Test retention threshold validation."""
        with pytest.raises(ValidationError):
            MemoryConsolidationConfig(
                session_id="session-123",
                retention_threshold=1.5,  # > 1.0
            )


class TestLocalInferenceConfig:
    """Tests for LocalInferenceConfig model."""

    def test_valid_config(self):
        """Test valid local inference config."""
        config = LocalInferenceConfig(
            model_id="llama-2-7b",
            max_tokens=4096,
            temperature=0.7,
        )
        assert config.model_id == "llama-2-7b"
        assert config.max_tokens == 4096
        assert config.temperature == 0.7


class TestGPUJobCreateRequest:
    """Tests for GPUJobCreateRequest model."""

    def test_valid_request(self):
        """Test valid job creation request."""
        config = EmbeddingJobConfig(repository_id="test-repo")
        request = GPUJobCreateRequest(
            job_type=GPUJobType.EMBEDDING_GENERATION,
            config=config,
            priority=GPUJobPriority.HIGH,
            gpu_memory_gb=16,
            max_runtime_hours=4,
        )
        assert request.job_type == GPUJobType.EMBEDDING_GENERATION
        assert request.priority == GPUJobPriority.HIGH
        assert request.gpu_memory_gb == 16
        assert request.max_runtime_hours == 4
        assert request.checkpoint_enabled is True  # default

    def test_gpu_memory_bounds(self):
        """Test GPU memory validation."""
        config = EmbeddingJobConfig(repository_id="test-repo")

        with pytest.raises(ValidationError):
            GPUJobCreateRequest(
                job_type=GPUJobType.EMBEDDING_GENERATION,
                config=config,
                gpu_memory_gb=2,  # Too low
            )

        with pytest.raises(ValidationError):
            GPUJobCreateRequest(
                job_type=GPUJobType.EMBEDDING_GENERATION,
                config=config,
                gpu_memory_gb=32,  # Too high
            )

    def test_max_runtime_bounds(self):
        """Test max runtime validation."""
        config = EmbeddingJobConfig(repository_id="test-repo")

        with pytest.raises(ValidationError):
            GPUJobCreateRequest(
                job_type=GPUJobType.EMBEDDING_GENERATION,
                config=config,
                max_runtime_hours=0,  # Too low
            )

        with pytest.raises(ValidationError):
            GPUJobCreateRequest(
                job_type=GPUJobType.EMBEDDING_GENERATION,
                config=config,
                max_runtime_hours=48,  # Too high
            )


class TestGPUJob:
    """Tests for GPUJob model."""

    def test_to_dynamodb_item(self, sample_gpu_job: GPUJob):
        """Test conversion to DynamoDB item."""
        item = sample_gpu_job.to_dynamodb_item()

        assert item["organization_id"] == sample_gpu_job.organization_id
        assert item["job_id"] == sample_gpu_job.job_id
        assert item["user_id"] == sample_gpu_job.user_id
        assert item["job_type"] == sample_gpu_job.job_type.value
        assert item["status"] == sample_gpu_job.status.value
        assert item["priority"] == sample_gpu_job.priority.value
        assert "org_status" in item
        assert (
            item["org_status"]
            == f"{sample_gpu_job.organization_id}#{sample_gpu_job.status.value}"
        )

    def test_from_dynamodb_item(self, sample_gpu_job: GPUJob):
        """Test creation from DynamoDB item."""
        item = sample_gpu_job.to_dynamodb_item()
        restored = GPUJob.from_dynamodb_item(item)

        assert restored.job_id == sample_gpu_job.job_id
        assert restored.organization_id == sample_gpu_job.organization_id
        assert restored.user_id == sample_gpu_job.user_id
        assert restored.job_type == sample_gpu_job.job_type
        assert restored.status == sample_gpu_job.status
        assert restored.priority == sample_gpu_job.priority

    def test_job_with_error(self):
        """Test job with error fields."""
        config = EmbeddingJobConfig(repository_id="test-repo")
        job = GPUJob(
            job_id="job-error-123",
            organization_id="org-123",
            user_id="user-123",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.FAILED,
            priority=GPUJobPriority.NORMAL,
            config=config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
            error_message="Out of memory",
            error_type=GPUJobErrorType.OOM,
        )

        item = job.to_dynamodb_item()
        assert item["error_message"] == "Out of memory"
        assert item["error_type"] == "oom"

        restored = GPUJob.from_dynamodb_item(item)
        assert restored.error_message == "Out of memory"
        assert restored.error_type == GPUJobErrorType.OOM


class TestGPUQuota:
    """Tests for GPUQuota model."""

    def test_to_dynamodb_item(self, sample_quota: GPUQuota):
        """Test conversion to DynamoDB item."""
        item = sample_quota.to_dynamodb_item()

        assert item["organization_id"] == sample_quota.organization_id
        assert item["quota_type"] == "QUOTA"
        assert item["max_concurrent_jobs"] == sample_quota.max_concurrent_jobs
        assert item["max_gpu_hours_monthly"] == sample_quota.max_gpu_hours_monthly

    def test_from_dynamodb_item(self, sample_quota: GPUQuota):
        """Test creation from DynamoDB item."""
        item = sample_quota.to_dynamodb_item()
        restored = GPUQuota.from_dynamodb_item(item)

        assert restored.organization_id == sample_quota.organization_id
        assert restored.max_concurrent_jobs == sample_quota.max_concurrent_jobs
        assert restored.max_gpu_hours_monthly == sample_quota.max_gpu_hours_monthly


class TestGPUResourceStatus:
    """Tests for GPUResourceStatus model."""

    def test_valid_status(self):
        """Test valid resource status."""
        status = GPUResourceStatus(
            gpus_available=2,
            gpus_total=4,
            gpus_in_use=2,
            queue_depth=5,
            estimated_wait_minutes=30,
            node_count=2,
            scaling_status="stable",
        )
        assert status.gpus_available == 2
        assert status.gpus_total == 4
        assert status.gpus_in_use == 2
        assert status.queue_depth == 5
        assert status.estimated_wait_minutes == 30
        assert status.node_count == 2
        assert status.scaling_status == "stable"
