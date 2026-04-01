"""Tests for GPU Scheduler API endpoints (ADR-061)."""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestGPUSchedulerEndpointsUnit:
    """Unit tests for GPU scheduler endpoint logic."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.gpu_scheduler")
            or key.startswith("src.services.gpu_scheduler")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    def test_request_model_validation(self):
        """Test request model validation."""
        from src.api.gpu_scheduler_endpoints import GPUJobSubmitRequest
        from src.services.gpu_scheduler.models import GPUJobPriority, GPUJobType

        # Valid request
        request = GPUJobSubmitRequest(
            job_type=GPUJobType.EMBEDDING_GENERATION,
            config={"repository_id": "test-repo"},
            priority=GPUJobPriority.HIGH,
            gpu_memory_gb=16,
            max_runtime_hours=4,
        )
        assert request.job_type == GPUJobType.EMBEDDING_GENERATION
        assert request.priority == GPUJobPriority.HIGH
        assert request.gpu_memory_gb == 16
        assert request.max_runtime_hours == 4
        assert request.checkpoint_enabled is True  # default

    def test_request_model_defaults(self):
        """Test request model default values."""
        from src.api.gpu_scheduler_endpoints import GPUJobSubmitRequest
        from src.services.gpu_scheduler.models import GPUJobPriority, GPUJobType

        request = GPUJobSubmitRequest(
            job_type=GPUJobType.LOCAL_INFERENCE,
            config={"model_id": "llama-2-7b"},
        )
        assert request.priority == GPUJobPriority.NORMAL
        assert request.gpu_memory_gb == 8
        assert request.max_runtime_hours == 2
        assert request.checkpoint_enabled is True

    def test_quota_update_request_validation(self):
        """Test quota update request model."""
        from src.api.gpu_scheduler_endpoints import GPUQuotaUpdateRequest

        request = GPUQuotaUpdateRequest(
            max_concurrent_jobs=10,
            max_gpu_hours_monthly=500,
            max_job_runtime_hours=12,
        )
        assert request.max_concurrent_jobs == 10
        assert request.max_gpu_hours_monthly == 500
        assert request.max_job_runtime_hours == 12

    def test_quota_update_request_partial(self):
        """Test quota update request with partial fields."""
        from src.api.gpu_scheduler_endpoints import GPUQuotaUpdateRequest

        request = GPUQuotaUpdateRequest(max_concurrent_jobs=5)
        assert request.max_concurrent_jobs == 5
        assert request.max_gpu_hours_monthly is None
        assert request.max_job_runtime_hours is None

    def test_response_models(self):
        """Test response model creation."""
        from src.api.gpu_scheduler_endpoints import (
            GPUJobListResponse,
            GPUJobResponse,
            GPUQuotaResponse,
            GPUResourceStatusResponse,
            HealthResponse,
        )

        # GPUJobResponse
        job_response = GPUJobResponse(
            job_id="job-123",
            organization_id="org-123",
            user_id="user-123",
            job_type="embedding_generation",
            status="queued",
            priority="normal",
            config={"repository_id": "test"},
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        assert job_response.job_id == "job-123"
        assert job_response.status == "queued"

        # GPUJobListResponse
        list_response = GPUJobListResponse(jobs=[job_response], count=1)
        assert list_response.count == 1

        # GPUQuotaResponse
        quota_response = GPUQuotaResponse(
            organization_id="org-123",
            max_concurrent_jobs=4,
            max_gpu_hours_monthly=100,
            max_job_runtime_hours=8,
            current_concurrent_jobs=0,
            current_month_gpu_hours=0.0,
        )
        assert quota_response.max_concurrent_jobs == 4

        # GPUResourceStatusResponse
        resource_response = GPUResourceStatusResponse(
            gpus_available=2,
            gpus_total=4,
            gpus_in_use=2,
            queue_depth=5,
            estimated_wait_minutes=30,
            node_count=2,
            scaling_status="stable",
        )
        assert resource_response.gpus_available == 2

        # HealthResponse
        health_response = HealthResponse(
            service="gpu_scheduler",
            healthy=True,
            region="us-east-1",
            jobs_table="aura-gpu-jobs-test",
            quotas_table="aura-gpu-quotas-test",
            queue_url="https://sqs.us-east-1.amazonaws.com/123/queue.fifo",
            dynamodb_status="healthy",
            sqs_status="healthy",
        )
        assert health_response.healthy is True


class TestParseJobConfig:
    """Tests for _parse_job_config helper function."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.gpu_scheduler")
            or key.startswith("src.services.gpu_scheduler")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    def test_parse_embedding_config(self):
        """Test parsing embedding job config."""
        from src.api.gpu_scheduler_endpoints import _parse_job_config
        from src.services.gpu_scheduler.models import EmbeddingJobConfig, GPUJobType

        config = _parse_job_config(
            GPUJobType.EMBEDDING_GENERATION,
            {"repository_id": "test-repo", "branch": "main"},
        )
        assert isinstance(config, EmbeddingJobConfig)
        assert config.repository_id == "test-repo"
        assert config.branch == "main"

    def test_parse_vulnerability_training_config(self):
        """Test parsing vulnerability training config."""
        from src.api.gpu_scheduler_endpoints import _parse_job_config
        from src.services.gpu_scheduler.models import (
            GPUJobType,
            VulnerabilityTrainingConfig,
        )

        config = _parse_job_config(
            GPUJobType.VULNERABILITY_TRAINING,
            {"dataset_id": "dataset-123", "epochs": 20},
        )
        assert isinstance(config, VulnerabilityTrainingConfig)
        assert config.dataset_id == "dataset-123"
        assert config.epochs == 20

    def test_parse_swe_rl_training_config(self):
        """Test parsing SWE-RL training config."""
        from src.api.gpu_scheduler_endpoints import _parse_job_config
        from src.services.gpu_scheduler.models import GPUJobType, SWERLTrainingConfig

        config = _parse_job_config(
            GPUJobType.SWE_RL_TRAINING,
            {"batch_id": "batch-123", "max_epochs": 200},
        )
        assert isinstance(config, SWERLTrainingConfig)
        assert config.batch_id == "batch-123"
        assert config.max_epochs == 200

    def test_parse_memory_consolidation_config(self):
        """Test parsing memory consolidation config."""
        from src.api.gpu_scheduler_endpoints import _parse_job_config
        from src.services.gpu_scheduler.models import (
            GPUJobType,
            MemoryConsolidationConfig,
        )

        config = _parse_job_config(
            GPUJobType.MEMORY_CONSOLIDATION,
            {"session_id": "session-123", "retention_threshold": 0.8},
        )
        assert isinstance(config, MemoryConsolidationConfig)
        assert config.session_id == "session-123"
        assert config.retention_threshold == 0.8

    def test_parse_local_inference_config(self):
        """Test parsing local inference config."""
        from src.api.gpu_scheduler_endpoints import _parse_job_config
        from src.services.gpu_scheduler.models import GPUJobType, LocalInferenceConfig

        config = _parse_job_config(
            GPUJobType.LOCAL_INFERENCE,
            {"model_id": "llama-2-7b", "max_tokens": 4096},
        )
        assert isinstance(config, LocalInferenceConfig)
        assert config.model_id == "llama-2-7b"
        assert config.max_tokens == 4096


class TestGPUJobResponseFromJob:
    """Tests for GPUJobResponse.from_job method."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.gpu_scheduler")
            or key.startswith("src.services.gpu_scheduler")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    def test_from_job_basic(self):
        """Test creating response from basic job."""
        from src.api.gpu_scheduler_endpoints import GPUJobResponse
        from src.services.gpu_scheduler.models import (
            EmbeddingJobConfig,
            GPUJob,
            GPUJobPriority,
            GPUJobStatus,
            GPUJobType,
        )

        config = EmbeddingJobConfig(repository_id="test-repo")
        job = GPUJob(
            job_id="job-123",
            organization_id="org-123",
            user_id="user-123",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.NORMAL,
            config=config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )

        response = GPUJobResponse.from_job(job)
        assert response.job_id == "job-123"
        assert response.organization_id == "org-123"
        assert response.status == "queued"
        assert response.job_type == "embedding_generation"

    def test_from_job_with_error(self):
        """Test creating response from failed job with error."""
        from src.api.gpu_scheduler_endpoints import GPUJobResponse
        from src.services.gpu_scheduler.models import (
            EmbeddingJobConfig,
            GPUJob,
            GPUJobErrorType,
            GPUJobPriority,
            GPUJobStatus,
            GPUJobType,
        )

        config = EmbeddingJobConfig(repository_id="test-repo")
        job = GPUJob(
            job_id="job-123",
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
            error_message="Out of GPU memory",
            error_type=GPUJobErrorType.OOM,
        )

        response = GPUJobResponse.from_job(job)
        assert response.status == "failed"
        assert response.error_message == "Out of GPU memory"
        assert response.error_type == "oom"


class TestGPUSchedulerEndpointsIntegration:
    """Integration tests with mocked services."""

    @pytest.fixture
    def mock_gpu_job(self):
        """Create a mock GPU job."""
        from src.services.gpu_scheduler.models import (
            EmbeddingJobConfig,
            GPUJob,
            GPUJobPriority,
            GPUJobStatus,
            GPUJobType,
        )

        config = EmbeddingJobConfig(repository_id="test-repo")
        return GPUJob(
            job_id="job-12345678",
            organization_id="org-123",
            user_id="user-456",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.NORMAL,
            config=config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            checkpoint_s3_path="s3://bucket/checkpoints/job-12345678/",
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def mock_quota(self):
        """Create a mock GPU quota."""
        from src.services.gpu_scheduler.models import GPUQuota

        return GPUQuota(
            organization_id="org-123",
            max_concurrent_jobs=4,
            max_gpu_hours_monthly=100,
            max_job_runtime_hours=8,
            current_concurrent_jobs=1,
            current_month_gpu_hours=10.5,
        )

    @pytest.fixture
    def mock_service(self, mock_gpu_job, mock_quota):
        """Create mock GPU scheduler service."""
        service = MagicMock()
        service.submit_job = AsyncMock(return_value=mock_gpu_job)
        service.get_job = AsyncMock(return_value=mock_gpu_job)
        service.list_jobs = AsyncMock(return_value=[mock_gpu_job])
        service.cancel_job = AsyncMock(return_value=mock_gpu_job)
        service.get_quota = AsyncMock(return_value=mock_quota)
        service.update_quota = AsyncMock(return_value=mock_quota)
        service.health_check = AsyncMock(
            return_value={
                "service": "gpu_scheduler",
                "healthy": True,
                "region": "us-east-1",
                "jobs_table": "aura-gpu-jobs-test",
                "quotas_table": "aura-gpu-quotas-test",
                "queue_url": "https://sqs.us-east-1.amazonaws.com/123/queue.fifo",
                "dynamodb_status": "healthy",
                "sqs_status": "healthy",
            }
        )
        return service

    @pytest.fixture
    def mock_k8s_client(self):
        """Create mock K8s client."""
        client = MagicMock()
        client.stream_pod_logs = MagicMock(
            return_value=iter(["Log line 1", "Log line 2"])
        )
        return client

    @pytest.mark.asyncio
    async def test_submit_job_direct(self, mock_service, mock_gpu_job):
        """Test submit_job endpoint function directly."""
        from src.api.gpu_scheduler_endpoints import GPUJobSubmitRequest, submit_job
        from src.services.gpu_scheduler.models import GPUJobType

        request = GPUJobSubmitRequest(
            job_type=GPUJobType.EMBEDDING_GENERATION,
            config={"repository_id": "test-repo"},
        )

        response = await submit_job(
            request=request,
            organization_id="org-123",
            user_id="user-456",
            service=mock_service,
        )

        assert response.job_id == "job-12345678"
        assert response.organization_id == "org-123"
        mock_service.submit_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_direct(self, mock_service, mock_gpu_job):
        """Test get_job endpoint function directly."""
        from src.api.gpu_scheduler_endpoints import get_job

        response = await get_job(
            job_id="job-12345678",
            organization_id="org-123",
            service=mock_service,
        )

        assert response.job_id == "job-12345678"
        mock_service.get_job.assert_called_once_with(
            organization_id="org-123",
            job_id="job-12345678",
        )

    @pytest.mark.asyncio
    async def test_list_jobs_direct(self, mock_service):
        """Test list_jobs endpoint function directly."""
        from src.api.gpu_scheduler_endpoints import list_jobs

        response = await list_jobs(
            organization_id="org-123",
            status=None,
            user_id=None,
            limit=50,
            service=mock_service,
        )

        assert response.count == 1
        assert len(response.jobs) == 1
        mock_service.list_jobs.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_job_direct(self, mock_service):
        """Test cancel_job endpoint function directly."""
        from src.api.gpu_scheduler_endpoints import cancel_job

        response = await cancel_job(
            job_id="job-12345678",
            organization_id="org-123",
            user_id="user-456",
            service=mock_service,
        )

        assert response.job_id == "job-12345678"
        mock_service.cancel_job.assert_called_once_with(
            organization_id="org-123",
            job_id="job-12345678",
            user_id="user-456",
        )

    @pytest.mark.asyncio
    async def test_get_quota_direct(self, mock_service):
        """Test get_quota endpoint function directly."""
        from src.api.gpu_scheduler_endpoints import get_quota

        response = await get_quota(
            organization_id="org-123",
            service=mock_service,
        )

        assert response.organization_id == "org-123"
        assert response.max_concurrent_jobs == 4
        mock_service.get_quota.assert_called_once_with(
            organization_id="org-123",
        )

    @pytest.mark.asyncio
    async def test_update_quota_direct(self, mock_service):
        """Test update_quota endpoint function directly."""
        from src.api.gpu_scheduler_endpoints import GPUQuotaUpdateRequest, update_quota

        request = GPUQuotaUpdateRequest(
            max_concurrent_jobs=10,
            max_gpu_hours_monthly=500,
        )

        response = await update_quota(
            request=request,
            organization_id="org-123",
            service=mock_service,
        )

        assert response.organization_id == "org-123"
        mock_service.update_quota.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_direct(self, mock_service):
        """Test health_check endpoint function directly."""
        from src.api.gpu_scheduler_endpoints import health_check

        response = await health_check(service=mock_service)

        assert response.service == "gpu_scheduler"
        assert response.healthy is True
        mock_service.health_check.assert_called_once()


class TestExceptionHandling:
    """Tests for exception handling in endpoints."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.gpu_scheduler")
            or key.startswith("src.services.gpu_scheduler")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    @pytest.mark.asyncio
    async def test_submit_job_quota_exceeded(self):
        """Test submit_job raises HTTPException when quota exceeded."""
        from src.api.gpu_scheduler_endpoints import GPUJobSubmitRequest, submit_job
        from src.services.gpu_scheduler.exceptions import QuotaExceededError
        from src.services.gpu_scheduler.models import GPUJobType

        mock_service = MagicMock()
        mock_service.submit_job = AsyncMock(
            side_effect=QuotaExceededError(
                organization_id="org-123",
                quota_type="concurrent_jobs",
                current_value=4,
                max_value=4,
            )
        )

        request = GPUJobSubmitRequest(
            job_type=GPUJobType.EMBEDDING_GENERATION,
            config={"repository_id": "test-repo"},
        )

        exc_raised = None
        try:
            await submit_job(
                request=request,
                organization_id="org-123",
                user_id="user-456",
                service=mock_service,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 429

    @pytest.mark.asyncio
    async def test_submit_job_invalid_config(self):
        """Test submit_job raises HTTPException for invalid config."""
        from src.api.gpu_scheduler_endpoints import GPUJobSubmitRequest, submit_job
        from src.services.gpu_scheduler.exceptions import InvalidJobConfigError
        from src.services.gpu_scheduler.models import GPUJobType

        mock_service = MagicMock()
        mock_service.submit_job = AsyncMock(
            side_effect=InvalidJobConfigError("Runtime exceeds quota limit")
        )

        # Use valid config format - the service will raise the error
        request = GPUJobSubmitRequest(
            job_type=GPUJobType.EMBEDDING_GENERATION,
            config={"repository_id": "valid-repo"},
            max_runtime_hours=24,  # Valid but service will reject
        )

        exc_raised = None
        try:
            await submit_job(
                request=request,
                organization_id="org-123",
                user_id="user-456",
                service=mock_service,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 400

    @pytest.mark.asyncio
    async def test_get_job_not_found(self):
        """Test get_job raises HTTPException for not found."""
        from src.api.gpu_scheduler_endpoints import get_job
        from src.services.gpu_scheduler.exceptions import GPUJobNotFoundError

        mock_service = MagicMock()
        mock_service.get_job = AsyncMock(
            side_effect=GPUJobNotFoundError("org-123", "non-existent")
        )

        exc_raised = None
        try:
            await get_job(
                job_id="non-existent",
                organization_id="org-123",
                service=mock_service,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self):
        """Test cancel_job raises HTTPException for not found."""
        from src.api.gpu_scheduler_endpoints import cancel_job
        from src.services.gpu_scheduler.exceptions import GPUJobNotFoundError

        mock_service = MagicMock()
        mock_service.cancel_job = AsyncMock(
            side_effect=GPUJobNotFoundError("org-123", "non-existent")
        )

        exc_raised = None
        try:
            await cancel_job(
                job_id="non-existent",
                organization_id="org-123",
                user_id="user-456",
                service=mock_service,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_job_already_completed(self):
        """Test cancel_job raises HTTPException for completed job."""
        from src.api.gpu_scheduler_endpoints import cancel_job
        from src.services.gpu_scheduler.exceptions import JobCancellationError

        mock_service = MagicMock()
        mock_service.cancel_job = AsyncMock(
            side_effect=JobCancellationError(
                "job-123",
                "Cannot cancel job with status: completed",
            )
        )

        exc_raised = None
        try:
            await cancel_job(
                job_id="job-123",
                organization_id="org-123",
                user_id="user-456",
                service=mock_service,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 409


class TestCostSummaryEndpoint:
    """Tests for cost summary endpoint."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.gpu_scheduler")
            or key.startswith("src.services.gpu_scheduler")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    @pytest.mark.asyncio
    async def test_get_cost_summary_with_jobs(self):
        """Test cost summary with completed jobs."""
        from src.api.gpu_scheduler_endpoints import get_cost_summary
        from src.services.gpu_scheduler.models import (
            EmbeddingJobConfig,
            GPUJob,
            GPUJobPriority,
            GPUJobStatus,
            GPUJobType,
        )

        config = EmbeddingJobConfig(repository_id="test-repo")
        now = datetime.now(timezone.utc)
        jobs = [
            GPUJob(
                job_id="job-1",
                organization_id="org-123",
                user_id="user-456",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.COMPLETED,
                priority=GPUJobPriority.NORMAL,
                config=config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=now,
                started_at=now,
                completed_at=now,
                cost_usd=1.50,
            ),
            GPUJob(
                job_id="job-2",
                organization_id="org-123",
                user_id="user-456",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.COMPLETED,
                priority=GPUJobPriority.NORMAL,
                config=config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=now,
                started_at=now,
                completed_at=now,
                cost_usd=2.50,
            ),
        ]

        mock_service = MagicMock()
        mock_service.list_jobs = AsyncMock(return_value=jobs)

        response = await get_cost_summary(
            organization_id="org-123",
            period="month",
            service=mock_service,
        )

        assert response.period == "month"
        assert response.total_cost_usd == 4.0
        assert response.job_count == 2
        assert "embedding_generation" in response.cost_by_job_type

    @pytest.mark.asyncio
    async def test_get_cost_summary_empty(self):
        """Test cost summary with no completed jobs."""
        from src.api.gpu_scheduler_endpoints import get_cost_summary

        mock_service = MagicMock()
        mock_service.list_jobs = AsyncMock(return_value=[])

        response = await get_cost_summary(
            organization_id="org-123",
            period="month",
            service=mock_service,
        )

        assert response.total_cost_usd == 0.0
        assert response.job_count == 0
        assert response.cost_by_job_type == {}


class TestResourceStatusEndpoint:
    """Tests for resource status endpoint."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.gpu_scheduler")
            or key.startswith("src.services.gpu_scheduler")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    @pytest.mark.asyncio
    async def test_get_resource_status(self):
        """Test get resource status."""
        from src.api.gpu_scheduler_endpoints import get_resource_status
        from src.services.gpu_scheduler.models import GPUResourceStatus

        mock_service = MagicMock()
        mock_service.get_resource_status = AsyncMock(
            return_value=GPUResourceStatus(
                gpus_available=2,
                gpus_total=4,
                gpus_in_use=2,
                queue_depth=5,
                estimated_wait_minutes=30,
                node_count=2,
                scaling_status="stable",
            )
        )

        response = await get_resource_status(service=mock_service)

        assert response.gpus_available == 2
        assert response.gpus_total == 4
        assert response.queue_depth == 5
        assert response.scaling_status == "stable"


class TestFactoryFunctions:
    """Tests for factory functions."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        import src.services.gpu_scheduler.gpu_scheduler_service as service_module

        service_module._gpu_scheduler_service = None
        yield

    def test_get_gpu_scheduler_service_creates_instance(self):
        """Test get_gpu_scheduler_service creates instance on first call."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "ENVIRONMENT": "test",
            },
        ):
            from src.services.gpu_scheduler.gpu_scheduler_service import (
                get_gpu_scheduler_service,
                init_gpu_scheduler_service,
            )

            # Initialize first
            init_gpu_scheduler_service()
            service = get_gpu_scheduler_service()

            assert service is not None


# =============================================================================
# Phase 2: Queue Management Endpoint Tests (ADR-061)
# =============================================================================


class TestQueuePositionEndpoint:
    """Tests for queue position endpoint."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.gpu_scheduler")
            or key.startswith("src.services.gpu_scheduler")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    @pytest.fixture
    def mock_position_estimate(self):
        """Create a mock position estimate."""
        from src.services.gpu_scheduler.models import PositionEstimate

        return PositionEstimate(
            job_id="job-12345678",
            queue_position=3,
            jobs_ahead=2,
            jobs_ahead_by_priority={"high": 1, "normal": 1, "low": 0},
            estimated_wait_minutes=15,
            estimated_start_time=datetime.now(timezone.utc),
            confidence=0.85,
            factors=["2 jobs ahead", "GPU scaling not required"],
            gpu_scaling_required=False,
            preemption_possible=False,
        )

    @pytest.mark.asyncio
    async def test_get_queue_position_success(self, mock_position_estimate):
        """Test getting queue position for a job."""
        from src.api.gpu_scheduler_endpoints import get_queue_position

        mock_service = MagicMock()
        mock_service.get_queue_position = AsyncMock(return_value=mock_position_estimate)

        response = await get_queue_position(
            job_id="job-12345678",
            organization_id="org-123",
            service=mock_service,
        )

        assert response.job_id == "job-12345678"
        assert response.queue_position == 3
        assert response.jobs_ahead == 2
        assert response.estimated_wait_minutes == 15
        assert response.confidence == 0.85
        mock_service.get_queue_position.assert_called_once_with(
            organization_id="org-123",
            job_id="job-12345678",
        )

    @pytest.mark.asyncio
    async def test_get_queue_position_not_found(self):
        """Test queue position for non-existent job."""
        from src.api.gpu_scheduler_endpoints import get_queue_position
        from src.services.gpu_scheduler.exceptions import GPUJobNotFoundError

        mock_service = MagicMock()
        mock_service.get_queue_position = AsyncMock(
            side_effect=GPUJobNotFoundError("org-123", "non-existent")
        )

        exc_raised = None
        try:
            await get_queue_position(
                job_id="non-existent",
                organization_id="org-123",
                service=mock_service,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 404


class TestQueueMetricsEndpoint:
    """Tests for queue metrics endpoint."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.gpu_scheduler")
            or key.startswith("src.services.gpu_scheduler")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    @pytest.fixture
    def mock_queue_metrics(self):
        """Create mock queue metrics."""
        from src.services.gpu_scheduler.models import QueueMetrics

        return QueueMetrics(
            total_queued=10,
            by_priority={"high": 2, "normal": 5, "low": 3},
            by_organization={"org-123": 6, "org-456": 4},
            running_jobs=4,
            running_by_priority={"high": 1, "normal": 2, "low": 1},
            avg_wait_time_seconds=300.0,
            oldest_queued_at=datetime.now(timezone.utc),
            estimated_drain_time_minutes=45,
            preemptions_last_hour=2,
            starvation_promotions_last_hour=1,
        )

    @pytest.mark.asyncio
    async def test_get_queue_metrics_success(self, mock_queue_metrics):
        """Test getting queue metrics."""
        from src.api.gpu_scheduler_endpoints import get_queue_metrics

        mock_service = MagicMock()
        mock_service.get_queue_metrics = AsyncMock(return_value=mock_queue_metrics)

        response = await get_queue_metrics(service=mock_service)

        assert response.total_queued == 10
        assert response.running_jobs == 4
        assert response.by_priority["high"] == 2
        assert response.by_priority["normal"] == 5
        assert response.estimated_drain_time_minutes == 45
        assert response.preemptions_last_hour == 2
        mock_service.get_queue_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_metrics_empty(self):
        """Test queue metrics when queue is empty."""
        from src.api.gpu_scheduler_endpoints import get_queue_metrics
        from src.services.gpu_scheduler.models import QueueMetrics

        empty_metrics = QueueMetrics(
            total_queued=0,
            by_priority={"high": 0, "normal": 0, "low": 0},
            by_organization={},
            running_jobs=0,
            running_by_priority={"high": 0, "normal": 0, "low": 0},
            avg_wait_time_seconds=0.0,
            oldest_queued_at=None,
            estimated_drain_time_minutes=0,
            preemptions_last_hour=0,
            starvation_promotions_last_hour=0,
        )

        mock_service = MagicMock()
        mock_service.get_queue_metrics = AsyncMock(return_value=empty_metrics)

        response = await get_queue_metrics(service=mock_service)

        assert response.total_queued == 0
        assert response.running_jobs == 0
        assert response.oldest_queued_at is None


class TestQueueEstimateEndpoint:
    """Tests for queue estimate endpoint."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.gpu_scheduler")
            or key.startswith("src.services.gpu_scheduler")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    @pytest.fixture
    def mock_position_estimate(self):
        """Create a mock position estimate for new job."""
        from src.services.gpu_scheduler.models import PositionEstimate

        return PositionEstimate(
            job_id="estimate",
            queue_position=5,
            jobs_ahead=4,
            jobs_ahead_by_priority={"high": 1, "normal": 2, "low": 1},
            estimated_wait_minutes=25,
            estimated_start_time=datetime.now(timezone.utc),
            confidence=0.7,
            factors=["4 jobs ahead", "GPU scaling required"],
            gpu_scaling_required=True,
            preemption_possible=False,
        )

    @pytest.mark.asyncio
    async def test_estimate_queue_position_success(self, mock_position_estimate):
        """Test estimating queue position for new job."""
        from src.api.gpu_scheduler_endpoints import (
            QueueEstimateRequest,
            estimate_queue_position,
        )
        from src.services.gpu_scheduler.models import GPUJobPriority, GPUJobType

        mock_service = MagicMock()
        mock_service.estimate_position_for_new_job = AsyncMock(
            return_value=mock_position_estimate
        )

        request = QueueEstimateRequest(
            priority=GPUJobPriority.NORMAL,
            job_type=GPUJobType.EMBEDDING_GENERATION,
        )

        response = await estimate_queue_position(
            request=request,
            organization_id="org-123",
            service=mock_service,
        )

        assert response.job_id == "estimate"
        assert response.queue_position == 5
        assert response.jobs_ahead == 4
        assert response.estimated_wait_minutes == 25
        assert response.gpu_scaling_required is True
        mock_service.estimate_position_for_new_job.assert_called_once_with(
            organization_id="org-123",
            priority=GPUJobPriority.NORMAL,
            job_type=GPUJobType.EMBEDDING_GENERATION,
        )

    @pytest.mark.asyncio
    async def test_estimate_high_priority_job(self, mock_position_estimate):
        """Test estimating position for high priority job."""
        from src.api.gpu_scheduler_endpoints import (
            QueueEstimateRequest,
            estimate_queue_position,
        )
        from src.services.gpu_scheduler.models import (
            GPUJobPriority,
            GPUJobType,
            PositionEstimate,
        )

        # High priority job estimate - shorter wait
        high_priority_estimate = PositionEstimate(
            job_id="estimate",
            queue_position=1,
            jobs_ahead=0,
            jobs_ahead_by_priority={"high": 0, "normal": 0, "low": 0},
            estimated_wait_minutes=5,
            estimated_start_time=datetime.now(timezone.utc),
            confidence=0.9,
            factors=["No jobs ahead", "High priority"],
            gpu_scaling_required=True,
            preemption_possible=True,
        )

        mock_service = MagicMock()
        mock_service.estimate_position_for_new_job = AsyncMock(
            return_value=high_priority_estimate
        )

        request = QueueEstimateRequest(
            priority=GPUJobPriority.HIGH,
            job_type=GPUJobType.SWE_RL_TRAINING,
        )

        response = await estimate_queue_position(
            request=request,
            organization_id="org-123",
            service=mock_service,
        )

        assert response.queue_position == 1
        assert response.preemption_possible is True
        assert response.estimated_wait_minutes == 5


class TestQueueResponseModels:
    """Tests for queue response model conversions."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.gpu_scheduler")
            or key.startswith("src.services.gpu_scheduler")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    def test_position_estimate_response_from_estimate(self):
        """Test creating PositionEstimateResponse from model."""
        from src.api.gpu_scheduler_endpoints import PositionEstimateResponse
        from src.services.gpu_scheduler.models import PositionEstimate

        estimate = PositionEstimate(
            job_id="job-123",
            queue_position=2,
            jobs_ahead=1,
            jobs_ahead_by_priority={"high": 0, "normal": 1, "low": 0},
            estimated_wait_minutes=10,
            estimated_start_time=datetime.now(timezone.utc),
            confidence=0.9,
            factors=["1 job ahead"],
            gpu_scaling_required=False,
            preemption_possible=False,
        )

        response = PositionEstimateResponse.from_estimate(estimate)

        assert response.job_id == "job-123"
        assert response.queue_position == 2
        assert response.jobs_ahead == 1
        assert response.confidence == 0.9

    def test_queue_metrics_response_from_metrics(self):
        """Test creating QueueMetricsResponse from model."""
        from src.api.gpu_scheduler_endpoints import QueueMetricsResponse
        from src.services.gpu_scheduler.models import QueueMetrics

        metrics = QueueMetrics(
            total_queued=15,
            by_priority={"high": 3, "normal": 7, "low": 5},
            by_organization={"org-1": 10, "org-2": 5},
            running_jobs=6,
            running_by_priority={"high": 2, "normal": 3, "low": 1},
            avg_wait_time_seconds=180.0,
            oldest_queued_at=datetime.now(timezone.utc),
            estimated_drain_time_minutes=60,
            preemptions_last_hour=3,
            starvation_promotions_last_hour=2,
        )

        response = QueueMetricsResponse.from_metrics(metrics)

        assert response.total_queued == 15
        assert response.running_jobs == 6
        assert response.by_priority["high"] == 3
        assert response.preemptions_last_hour == 3

    def test_queue_estimate_request_validation(self):
        """Test QueueEstimateRequest validation."""
        from src.api.gpu_scheduler_endpoints import QueueEstimateRequest
        from src.services.gpu_scheduler.models import GPUJobPriority, GPUJobType

        request = QueueEstimateRequest(
            priority=GPUJobPriority.HIGH,
            job_type=GPUJobType.VULNERABILITY_TRAINING,
        )

        assert request.priority == GPUJobPriority.HIGH
        assert request.job_type == GPUJobType.VULNERABILITY_TRAINING
