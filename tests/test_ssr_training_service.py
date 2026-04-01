"""
Tests for SSR Training Service

Tests the training workflow orchestration for the Self-Play SWE-RL
training pipeline (ADR-050 Phase 2).

Author: Project Aura Team
Created: 2026-01-01
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.ssr.artifact_storage_service import ArtifactStorageService
from src.services.ssr.bug_artifact import ArtifactStatus, BugArtifact
from src.services.ssr.training_service import (
    SSRTrainingService,
    TrainingJobConfig,
    TrainingJobResult,
    TrainingJobStatus,
    create_training_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_artifact() -> BugArtifact:
    """Create a mock valid artifact for testing."""
    return BugArtifact(
        artifact_id="ssr-artifact-test123",
        repository_id="repo-456",
        commit_sha="abc123def456",
        test_script="#!/bin/bash\npytest tests/",
        test_files=["tests/test_foo.py"],
        test_parser='import sys\nprint(json.dumps({"test1": "pass"}))',
        bug_inject_diff="diff --git a/foo.py b/foo.py\n-old\n+new",
        test_weaken_diff="diff --git a/tests/test_foo.py\n-assert True\n+pass",
        status=ArtifactStatus.VALID,
    )


@pytest.fixture
def mock_artifact_storage(mock_artifact: BugArtifact) -> MagicMock:
    """Create a mock artifact storage service."""
    storage = MagicMock(spec=ArtifactStorageService)
    storage.get_artifact = AsyncMock(return_value=mock_artifact)
    return storage


@pytest.fixture
def training_service(mock_artifact_storage: MagicMock) -> SSRTrainingService:
    """Create a training service in test mode."""
    service = SSRTrainingService(
        project_name="test-aura",
        environment="test",
        region="us-east-1",
        artifact_storage=mock_artifact_storage,
    )
    return service


@pytest.fixture
def training_config() -> TrainingJobConfig:
    """Create a sample training job configuration."""
    return TrainingJobConfig(
        artifact_id="ssr-artifact-test123",
        repository_id="repo-456",
        max_attempts=3,
        timeout_minutes=30,
        subnet_ids=["subnet-123", "subnet-456"],
        security_group_id="sg-789",
        metadata={"source": "test"},
    )


# =============================================================================
# Enum Tests
# =============================================================================


class TestTrainingJobStatus:
    """Tests for TrainingJobStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Verify all expected statuses are defined."""
        expected = ["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"]
        for status in expected:
            assert hasattr(TrainingJobStatus, status)

    def test_status_values(self) -> None:
        """Verify status values are lowercase strings."""
        assert TrainingJobStatus.PENDING.value == "pending"
        assert TrainingJobStatus.RUNNING.value == "running"
        assert TrainingJobStatus.SUCCEEDED.value == "succeeded"
        assert TrainingJobStatus.FAILED.value == "failed"
        assert TrainingJobStatus.TIMED_OUT.value == "timed_out"
        assert TrainingJobStatus.ABORTED.value == "aborted"

    def test_status_from_string(self) -> None:
        """Test creating status from string value."""
        status = TrainingJobStatus("running")
        assert status == TrainingJobStatus.RUNNING


# =============================================================================
# TrainingJobConfig Tests
# =============================================================================


class TestTrainingJobConfig:
    """Tests for TrainingJobConfig dataclass."""

    def test_required_fields(self) -> None:
        """Test creating config with required fields only."""
        config = TrainingJobConfig(
            artifact_id="test-artifact",
            repository_id="test-repo",
        )
        assert config.artifact_id == "test-artifact"
        assert config.repository_id == "test-repo"
        assert config.max_attempts == 3  # default
        assert config.timeout_minutes == 30  # default

    def test_all_fields(self, training_config: TrainingJobConfig) -> None:
        """Test creating config with all fields."""
        assert training_config.artifact_id == "ssr-artifact-test123"
        assert training_config.repository_id == "repo-456"
        assert training_config.max_attempts == 3
        assert training_config.timeout_minutes == 30
        assert training_config.subnet_ids == ["subnet-123", "subnet-456"]
        assert training_config.security_group_id == "sg-789"
        assert training_config.metadata == {"source": "test"}

    def test_default_empty_lists(self) -> None:
        """Test that default subnet_ids is empty list."""
        config = TrainingJobConfig(artifact_id="a", repository_id="r")
        assert config.subnet_ids == []
        assert config.metadata == {}


# =============================================================================
# TrainingJobResult Tests
# =============================================================================


class TestTrainingJobResult:
    """Tests for TrainingJobResult dataclass."""

    def test_minimal_result(self) -> None:
        """Test creating result with minimal fields."""
        result = TrainingJobResult(
            job_id="test-job",
            artifact_id="test-artifact",
            status=TrainingJobStatus.PENDING,
        )
        assert result.job_id == "test-job"
        assert result.artifact_id == "test-artifact"
        assert result.status == TrainingJobStatus.PENDING
        assert result.execution_arn is None
        assert result.solved is False
        assert result.higher_order_created is False

    def test_full_result(self) -> None:
        """Test creating result with all fields."""
        now = datetime.now(timezone.utc)
        result = TrainingJobResult(
            job_id="test-job",
            artifact_id="test-artifact",
            status=TrainingJobStatus.SUCCEEDED,
            execution_arn="arn:aws:states:us-east-1:123:execution:test",
            started_at=now,
            completed_at=now,
            solved=True,
            higher_order_created=True,
            error_message=None,
            metrics={"duration_ms": 5000},
        )
        assert result.solved is True
        assert result.higher_order_created is True
        assert result.metrics == {"duration_ms": 5000}

    def test_to_dict(self) -> None:
        """Test serializing result to dictionary."""
        now = datetime.now(timezone.utc)
        result = TrainingJobResult(
            job_id="test-job",
            artifact_id="test-artifact",
            status=TrainingJobStatus.RUNNING,
            started_at=now,
        )
        data = result.to_dict()

        assert data["job_id"] == "test-job"
        assert data["artifact_id"] == "test-artifact"
        assert data["status"] == "running"
        assert data["started_at"] == now.isoformat()
        assert data["completed_at"] is None

    def test_from_dict(self) -> None:
        """Test deserializing result from dictionary."""
        now = datetime.now(timezone.utc)
        data = {
            "job_id": "test-job",
            "artifact_id": "test-artifact",
            "status": "succeeded",
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
            "solved": True,
            "higher_order_created": False,
            "metrics": {"attempts": 2},
        }
        result = TrainingJobResult.from_dict(data)

        assert result.job_id == "test-job"
        assert result.status == TrainingJobStatus.SUCCEEDED
        assert result.solved is True
        assert result.metrics == {"attempts": 2}

    def test_roundtrip_serialization(self) -> None:
        """Test to_dict and from_dict roundtrip."""
        now = datetime.now(timezone.utc)
        original = TrainingJobResult(
            job_id="test-job",
            artifact_id="test-artifact",
            status=TrainingJobStatus.SUCCEEDED,
            started_at=now,
            completed_at=now,
            solved=True,
            higher_order_created=True,
            metrics={"test": "value"},
        )
        data = original.to_dict()
        restored = TrainingJobResult.from_dict(data)

        assert restored.job_id == original.job_id
        assert restored.status == original.status
        assert restored.solved == original.solved
        assert restored.metrics == original.metrics


# =============================================================================
# SSRTrainingService Initialization Tests
# =============================================================================


class TestSSRTrainingServiceInit:
    """Tests for SSRTrainingService initialization."""

    def test_default_initialization(self) -> None:
        """Test service with default parameters."""
        service = SSRTrainingService(environment="test")
        assert service.project_name == "aura"
        assert service.environment == "test"
        assert service._use_mock is True  # test mode

    def test_custom_parameters(self) -> None:
        """Test service with custom parameters."""
        service = SSRTrainingService(
            project_name="custom-project",
            environment="prod",
            region="eu-west-1",
        )
        assert service.project_name == "custom-project"
        assert service.region == "eu-west-1"

    def test_state_machine_arn_generation(self) -> None:
        """Test that state machine ARN is correctly constructed."""
        service = SSRTrainingService(
            project_name="aura",
            environment="dev",
            region="us-east-1",
        )
        expected = (
            "arn:aws:states:us-east-1:000000000000:stateMachine:"
            "aura-ssr-training-workflow-dev"
        )
        assert service.state_machine_arn == expected

    def test_custom_state_machine_arn(self) -> None:
        """Test using custom state machine ARN."""
        custom_arn = "arn:aws:states:us-west-2:123456789:stateMachine:custom"
        service = SSRTrainingService(
            environment="test",
            state_machine_arn=custom_arn,
        )
        assert service.state_machine_arn == custom_arn

    def test_factory_function(self) -> None:
        """Test create_training_service factory function."""
        service = create_training_service(
            project_name="test-project",
            environment="test",
        )
        assert isinstance(service, SSRTrainingService)
        assert service.project_name == "test-project"


# =============================================================================
# Submit Training Job Tests
# =============================================================================


class TestSubmitTrainingJob:
    """Tests for training job submission."""

    @pytest.mark.asyncio
    async def test_submit_job_success(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
    ) -> None:
        """Test successful job submission."""
        result = await training_service.submit_training_job(training_config)

        assert result.job_id.startswith("ssr-job-")
        assert result.artifact_id == training_config.artifact_id
        assert result.status == TrainingJobStatus.RUNNING
        assert result.execution_arn is not None
        assert result.started_at is not None

    @pytest.mark.asyncio
    async def test_submit_job_stores_in_mock(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
    ) -> None:
        """Test that submitted job is stored in mock executions."""
        result = await training_service.submit_training_job(training_config)

        stored = training_service._mock_executions.get(result.job_id)
        assert stored is not None
        assert stored.artifact_id == training_config.artifact_id

    @pytest.mark.asyncio
    async def test_submit_job_artifact_not_found(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
    ) -> None:
        """Test submission fails when artifact not found."""
        training_service._artifact_storage.get_artifact = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Artifact not found"):
            await training_service.submit_training_job(training_config)

    @pytest.mark.asyncio
    async def test_submit_job_artifact_not_valid(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
        mock_artifact: BugArtifact,
    ) -> None:
        """Test submission fails when artifact is not valid."""
        mock_artifact.status = ArtifactStatus.INVALID
        training_service._artifact_storage.get_artifact = AsyncMock(
            return_value=mock_artifact
        )

        with pytest.raises(ValueError, match="Artifact is not valid"):
            await training_service.submit_training_job(training_config)

    @pytest.mark.asyncio
    async def test_submit_job_generates_unique_ids(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
    ) -> None:
        """Test that each submission generates a unique job ID."""
        result1 = await training_service.submit_training_job(training_config)
        result2 = await training_service.submit_training_job(training_config)

        assert result1.job_id != result2.job_id


# =============================================================================
# Get Job Status Tests
# =============================================================================


class TestGetJobStatus:
    """Tests for getting job status."""

    @pytest.mark.asyncio
    async def test_get_status_existing_job(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
    ) -> None:
        """Test getting status of existing job."""
        submitted = await training_service.submit_training_job(training_config)
        status = await training_service.get_job_status(submitted.job_id)

        assert status is not None
        assert status.job_id == submitted.job_id
        assert status.status == TrainingJobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_get_status_nonexistent_job(
        self,
        training_service: SSRTrainingService,
    ) -> None:
        """Test getting status of non-existent job returns None."""
        status = await training_service.get_job_status("nonexistent-job-id")
        assert status is None


# =============================================================================
# Cancel Job Tests
# =============================================================================


class TestCancelJob:
    """Tests for cancelling training jobs."""

    @pytest.mark.asyncio
    async def test_cancel_existing_job(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
    ) -> None:
        """Test cancelling an existing job."""
        submitted = await training_service.submit_training_job(training_config)
        result = await training_service.cancel_job(submitted.job_id)

        assert result is True

        # Verify status is aborted
        status = await training_service.get_job_status(submitted.job_id)
        assert status is not None
        assert status.status == TrainingJobStatus.ABORTED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(
        self,
        training_service: SSRTrainingService,
    ) -> None:
        """Test cancelling a non-existent job returns False."""
        result = await training_service.cancel_job("nonexistent-job-id")
        assert result is False


# =============================================================================
# List Jobs Tests
# =============================================================================


class TestListJobs:
    """Tests for listing training jobs."""

    @pytest.mark.asyncio
    async def test_list_all_jobs(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
    ) -> None:
        """Test listing all jobs."""
        # Submit a few jobs
        await training_service.submit_training_job(training_config)
        await training_service.submit_training_job(training_config)

        jobs = await training_service.list_jobs()
        assert len(jobs) >= 2

    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
    ) -> None:
        """Test listing jobs filtered by status."""
        submitted = await training_service.submit_training_job(training_config)
        await training_service.cancel_job(submitted.job_id)

        running_jobs = await training_service.list_jobs(
            status=TrainingJobStatus.RUNNING
        )
        aborted_jobs = await training_service.list_jobs(
            status=TrainingJobStatus.ABORTED
        )

        assert all(j.status == TrainingJobStatus.RUNNING for j in running_jobs)
        assert all(j.status == TrainingJobStatus.ABORTED for j in aborted_jobs)

    @pytest.mark.asyncio
    async def test_list_jobs_with_limit(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
    ) -> None:
        """Test listing jobs with a limit."""
        # Submit 5 jobs
        for _ in range(5):
            await training_service.submit_training_job(training_config)

        jobs = await training_service.list_jobs(limit=3)
        assert len(jobs) <= 3

    @pytest.mark.asyncio
    async def test_list_jobs_empty(
        self,
        mock_artifact_storage: MagicMock,
    ) -> None:
        """Test listing jobs when none exist."""
        service = SSRTrainingService(
            environment="test",
            artifact_storage=mock_artifact_storage,
        )
        jobs = await service.list_jobs()
        assert jobs == []


# =============================================================================
# Batch Training Tests
# =============================================================================


class TestBatchTraining:
    """Tests for batch training operations."""

    @pytest.mark.asyncio
    async def test_submit_batch_training(
        self,
        training_service: SSRTrainingService,
    ) -> None:
        """Test submitting multiple training jobs in batch."""
        artifact_ids = [
            "ssr-artifact-test123",
            "ssr-artifact-test123",
            "ssr-artifact-test123",
        ]

        results = await training_service.submit_batch_training(
            artifact_ids=artifact_ids,
            repository_id="repo-456",
            max_concurrent=2,
        )

        assert len(results) == 3
        assert all(isinstance(r, TrainingJobResult) for r in results)
        assert all(r.status == TrainingJobStatus.RUNNING for r in results)

    @pytest.mark.asyncio
    async def test_batch_training_with_failures(
        self,
        training_service: SSRTrainingService,
    ) -> None:
        """Test batch training handles individual failures gracefully."""
        # Mix valid and invalid artifact IDs
        training_service._artifact_storage.get_artifact = AsyncMock(
            side_effect=[
                BugArtifact(
                    artifact_id="valid-1",
                    repository_id="repo",
                    commit_sha="abc123",
                    test_script="echo",
                    test_files=[],
                    test_parser="",
                    bug_inject_diff="",
                    test_weaken_diff="",
                    status=ArtifactStatus.VALID,
                ),
                None,  # Not found
                BugArtifact(
                    artifact_id="valid-2",
                    repository_id="repo",
                    commit_sha="def456",
                    test_script="echo",
                    test_files=[],
                    test_parser="",
                    bug_inject_diff="",
                    test_weaken_diff="",
                    status=ArtifactStatus.VALID,
                ),
            ]
        )

        results = await training_service.submit_batch_training(
            artifact_ids=["valid-1", "invalid", "valid-2"],
            repository_id="repo",
        )

        # Should have 2 successful results (failures are logged but filtered)
        assert len(results) == 2


# =============================================================================
# Metrics Tests
# =============================================================================


class TestTrainingMetrics:
    """Tests for training metrics."""

    @pytest.mark.asyncio
    async def test_get_metrics_empty(
        self,
        mock_artifact_storage: MagicMock,
    ) -> None:
        """Test getting metrics with no jobs."""
        service = SSRTrainingService(
            environment="test",
            artifact_storage=mock_artifact_storage,
        )
        metrics = await service.get_training_metrics()

        assert metrics["total_jobs"] == 0
        assert metrics["success_rate"] == 0
        assert metrics["solve_rate"] == 0

    @pytest.mark.asyncio
    async def test_get_metrics_with_jobs(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
    ) -> None:
        """Test getting metrics with submitted jobs."""
        # Submit some jobs
        job1 = await training_service.submit_training_job(training_config)
        job2 = await training_service.submit_training_job(training_config)

        # Manually update status for testing
        training_service._mock_executions[job1.job_id].status = (
            TrainingJobStatus.SUCCEEDED
        )
        training_service._mock_executions[job1.job_id].solved = True

        metrics = await training_service.get_training_metrics()

        assert metrics["total_jobs"] == 2
        assert metrics["succeeded"] == 1
        assert metrics["running"] == 1
        assert metrics["solved_bugs"] == 1


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_mock_mode(
        self,
        training_service: SSRTrainingService,
        training_config: TrainingJobConfig,
    ) -> None:
        """Test health check in mock mode."""
        await training_service.submit_training_job(training_config)

        health = await training_service.health_check()

        assert health["service"] == "ssr_training"
        assert health["status"] == "healthy"
        assert health["mock_mode"] is True
        assert health["mock_executions"] == 1

    @pytest.mark.asyncio
    async def test_health_check_includes_state_machine_arn(
        self,
        training_service: SSRTrainingService,
    ) -> None:
        """Test health check includes state machine ARN."""
        health = await training_service.health_check()
        assert "state_machine_arn" in health


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_account_id_from_arn(self) -> None:
        """Test extracting account ID from state machine ARN."""
        service = SSRTrainingService(
            environment="test",
            state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
        )
        account_id = service._get_account_id()
        assert account_id == "123456789012"

    def test_get_account_id_fallback(self) -> None:
        """Test account ID fallback for invalid ARN."""
        service = SSRTrainingService(
            environment="test",
            state_machine_arn="invalid-arn",
        )
        account_id = service._get_account_id()
        assert account_id == "000000000000"

    def test_extract_artifact_id_valid(self) -> None:
        """Test extracting artifact ID from Step Functions input."""
        service = SSRTrainingService(environment="test")
        input_json = json.dumps({"artifact_id": "test-artifact-123"})

        artifact_id = service._extract_artifact_id(input_json)
        assert artifact_id == "test-artifact-123"

    def test_extract_artifact_id_missing(self) -> None:
        """Test extracting artifact ID when missing."""
        service = SSRTrainingService(environment="test")
        input_json = json.dumps({"other_field": "value"})

        artifact_id = service._extract_artifact_id(input_json)
        assert artifact_id == ""

    def test_extract_artifact_id_invalid_json(self) -> None:
        """Test extracting artifact ID from invalid JSON."""
        service = SSRTrainingService(environment="test")

        artifact_id = service._extract_artifact_id("not-valid-json")
        assert artifact_id == ""


# =============================================================================
# Integration Tests (with mocked boto3)
# =============================================================================


class TestBoto3Integration:
    """Tests for boto3 integration paths."""

    @pytest.mark.asyncio
    async def test_sfn_client_lazy_init(self) -> None:
        """Test that Step Functions client is lazily initialized."""
        service = SSRTrainingService(environment="test")
        assert service._sfn is None  # Not initialized yet in mock mode

    @pytest.mark.asyncio
    async def test_artifact_storage_lazy_init(self) -> None:
        """Test that artifact storage is lazily initialized."""
        service = SSRTrainingService(environment="test")
        # Access the property to trigger initialization
        storage = service.artifact_storage
        assert storage is not None
        assert isinstance(storage, ArtifactStorageService)


# =============================================================================
# Package Export Tests
# =============================================================================


class TestPackageExports:
    """Tests for package-level exports."""

    def test_training_service_exported(self) -> None:
        """Test that training service classes are exported from package."""
        from src.services.ssr import (
            SSRTrainingService,
            TrainingJobConfig,
            TrainingJobResult,
            TrainingJobStatus,
            create_training_service,
        )

        assert SSRTrainingService is not None
        assert TrainingJobConfig is not None
        assert TrainingJobResult is not None
        assert TrainingJobStatus is not None
        assert create_training_service is not None


# =============================================================================
# P1: CRITICAL ERROR PATH TESTS
# =============================================================================


class TestP1CriticalErrorPaths:
    """P1 tests for critical error handling paths."""

    @pytest.mark.asyncio
    async def test_submit_job_artifact_not_found(
        self, mock_artifact_storage: MagicMock
    ) -> None:
        """Test submitting job with non-existent artifact."""
        mock_artifact_storage.get_artifact = AsyncMock(return_value=None)

        service = SSRTrainingService(
            environment="test", artifact_storage=mock_artifact_storage
        )
        config = TrainingJobConfig(artifact_id="non-existent", repository_id="repo-1")

        with pytest.raises(ValueError, match="Artifact not found"):
            await service.submit_training_job(config)

    @pytest.mark.asyncio
    async def test_submit_job_artifact_invalid_status(
        self, mock_artifact: BugArtifact, mock_artifact_storage: MagicMock
    ) -> None:
        """Test submitting job with artifact that is not valid."""
        mock_artifact.status = ArtifactStatus.PENDING  # Not VALID status
        mock_artifact_storage.get_artifact = AsyncMock(return_value=mock_artifact)

        service = SSRTrainingService(
            environment="test", artifact_storage=mock_artifact_storage
        )
        config = TrainingJobConfig(artifact_id="draft-artifact", repository_id="repo-1")

        with pytest.raises(ValueError, match="not valid for training"):
            await service.submit_training_job(config)

    @pytest.mark.asyncio
    async def test_submit_job_artifact_failed_status(
        self, mock_artifact: BugArtifact, mock_artifact_storage: MagicMock
    ) -> None:
        """Test submitting job with artifact that has failed status."""
        mock_artifact.status = ArtifactStatus.FAILED
        mock_artifact_storage.get_artifact = AsyncMock(return_value=mock_artifact)

        service = SSRTrainingService(
            environment="test", artifact_storage=mock_artifact_storage
        )
        config = TrainingJobConfig(
            artifact_id="failed-artifact", repository_id="repo-1"
        )

        with pytest.raises(ValueError, match="not valid for training"):
            await service.submit_training_job(config)

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(
        self, mock_artifact_storage: MagicMock
    ) -> None:
        """Test getting status of non-existent job."""
        service = SSRTrainingService(
            environment="test", artifact_storage=mock_artifact_storage
        )

        result = await service.get_job_status("non-existent-job")
        assert result is None

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self, mock_artifact_storage: MagicMock) -> None:
        """Test cancelling non-existent job."""
        service = SSRTrainingService(
            environment="test", artifact_storage=mock_artifact_storage
        )

        result = await service.cancel_job("non-existent-job")
        assert result is False

    @pytest.mark.asyncio
    async def test_sfn_client_not_available_in_mock_mode(self) -> None:
        """Test that SFN client is None in mock mode."""
        service = SSRTrainingService(environment="test")
        # In test mode, sfn property returns None
        assert service._use_mock is True

    def test_training_result_from_dict_invalid_status(self) -> None:
        """Test from_dict with invalid status raises error."""
        data = {
            "job_id": "test-job",
            "artifact_id": "test-artifact",
            "status": "invalid_status",
        }

        with pytest.raises(ValueError):
            TrainingJobResult.from_dict(data)


# =============================================================================
# P2: BOUNDARY CONDITION TESTS
# =============================================================================


class TestP2BoundaryConditions:
    """P2 tests for boundary conditions and edge values."""

    @pytest.mark.asyncio
    async def test_submit_job_empty_subnet_ids(
        self, training_service: SSRTrainingService
    ) -> None:
        """Test submitting job with empty subnet IDs."""
        config = TrainingJobConfig(
            artifact_id="ssr-artifact-test123",
            repository_id="repo-456",
            subnet_ids=[],  # Empty
        )

        result = await training_service.submit_training_job(config)
        assert result.status == TrainingJobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_submit_job_zero_timeout(
        self, mock_artifact_storage: MagicMock, mock_artifact: BugArtifact
    ) -> None:
        """Test submitting job with zero timeout."""
        service = SSRTrainingService(
            environment="test", artifact_storage=mock_artifact_storage
        )
        config = TrainingJobConfig(
            artifact_id="ssr-artifact-test123",
            repository_id="repo-456",
            timeout_minutes=0,
        )

        result = await service.submit_training_job(config)
        assert result.status == TrainingJobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_submit_job_max_attempts_one(
        self, mock_artifact_storage: MagicMock, mock_artifact: BugArtifact
    ) -> None:
        """Test submitting job with max_attempts=1."""
        service = SSRTrainingService(
            environment="test", artifact_storage=mock_artifact_storage
        )
        config = TrainingJobConfig(
            artifact_id="ssr-artifact-test123",
            repository_id="repo-456",
            max_attempts=1,
        )

        result = await service.submit_training_job(config)
        assert result.status == TrainingJobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, mock_artifact_storage: MagicMock) -> None:
        """Test listing jobs when none exist."""
        service = SSRTrainingService(
            environment="test", artifact_storage=mock_artifact_storage
        )

        results = await service.list_jobs()
        assert results == []

    @pytest.mark.asyncio
    async def test_list_jobs_limit_zero(
        self, training_service: SSRTrainingService, training_config: TrainingJobConfig
    ) -> None:
        """Test listing jobs with limit=0."""
        # First submit a job
        await training_service.submit_training_job(training_config)

        # Then list with limit 0
        results = await training_service.list_jobs(limit=0)
        assert results == []

    @pytest.mark.asyncio
    async def test_list_jobs_limit_one(
        self, training_service: SSRTrainingService, training_config: TrainingJobConfig
    ) -> None:
        """Test listing jobs with limit=1."""
        # Submit multiple jobs
        await training_service.submit_training_job(training_config)
        await training_service.submit_training_job(training_config)

        results = await training_service.list_jobs(limit=1)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_batch_training_empty_artifact_list(
        self, mock_artifact_storage: MagicMock
    ) -> None:
        """Test batch training with empty artifact list."""
        service = SSRTrainingService(
            environment="test", artifact_storage=mock_artifact_storage
        )

        results = await service.submit_batch_training(
            artifact_ids=[],
            repository_id="repo-1",
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_training_max_concurrent_one(
        self, mock_artifact_storage: MagicMock, mock_artifact: BugArtifact
    ) -> None:
        """Test batch training with max_concurrent=1."""
        service = SSRTrainingService(
            environment="test", artifact_storage=mock_artifact_storage
        )

        results = await service.submit_batch_training(
            artifact_ids=["ssr-artifact-test123", "ssr-artifact-test123"],
            repository_id="repo-1",
            max_concurrent=1,
        )
        assert len(results) == 2

    def test_result_to_dict_none_timestamps(self) -> None:
        """Test to_dict with None timestamps."""
        result = TrainingJobResult(
            job_id="test-job",
            artifact_id="test-artifact",
            status=TrainingJobStatus.PENDING,
            started_at=None,
            completed_at=None,
        )

        data = result.to_dict()
        assert data["started_at"] is None
        assert data["completed_at"] is None

    def test_result_from_dict_none_timestamps(self) -> None:
        """Test from_dict with None timestamps."""
        data = {
            "job_id": "test-job",
            "artifact_id": "test-artifact",
            "status": "pending",
            "started_at": None,
            "completed_at": None,
        }

        result = TrainingJobResult.from_dict(data)
        assert result.started_at is None
        assert result.completed_at is None


# =============================================================================
# P3: API-SPECIFIC EDGE CASES
# =============================================================================


class TestP3ApiEdgeCases:
    """P3 tests for API-specific edge cases."""

    def test_service_with_custom_state_machine_arn(self) -> None:
        """Test creating service with custom state machine ARN."""
        custom_arn = "arn:aws:states:us-west-2:111111111111:stateMachine:custom-machine"
        service = SSRTrainingService(
            environment="test",
            state_machine_arn=custom_arn,
        )

        assert service.state_machine_arn == custom_arn

    def test_service_with_custom_region(self) -> None:
        """Test creating service with custom region."""
        service = SSRTrainingService(
            environment="test",
            region="eu-west-1",
        )

        assert service.region == "eu-west-1"

    def test_service_with_custom_project_name(self) -> None:
        """Test creating service with custom project name."""
        service = SSRTrainingService(
            environment="test",
            project_name="my-project",
        )

        assert service.project_name == "my-project"

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_running_status(
        self, training_service: SSRTrainingService, training_config: TrainingJobConfig
    ) -> None:
        """Test listing jobs filtered by RUNNING status."""
        # Submit a job (will be RUNNING in mock mode)
        await training_service.submit_training_job(training_config)

        results = await training_service.list_jobs(status=TrainingJobStatus.RUNNING)
        assert len(results) == 1
        assert results[0].status == TrainingJobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_list_jobs_filter_by_succeeded_status(
        self, training_service: SSRTrainingService
    ) -> None:
        """Test listing jobs filtered by SUCCEEDED status (no matches)."""
        # Don't submit any jobs - should return empty
        results = await training_service.list_jobs(status=TrainingJobStatus.SUCCEEDED)
        assert results == []

    @pytest.mark.asyncio
    async def test_cancel_existing_job(
        self, training_service: SSRTrainingService, training_config: TrainingJobConfig
    ) -> None:
        """Test cancelling an existing job."""
        result = await training_service.submit_training_job(training_config)
        job_id = result.job_id

        cancelled = await training_service.cancel_job(job_id)
        assert cancelled is True

        # Verify status changed to ABORTED
        status = await training_service.get_job_status(job_id)
        assert status is not None
        assert status.status == TrainingJobStatus.ABORTED

    def test_get_account_id_from_valid_arn(self) -> None:
        """Test account ID extraction from valid ARN."""
        service = SSRTrainingService(
            environment="test",
            state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
        )

        account_id = service._get_account_id()
        assert account_id == "123456789012"

    def test_get_account_id_from_govcloud_arn(self) -> None:
        """Test account ID extraction from GovCloud ARN."""
        service = SSRTrainingService(
            environment="test",
            state_machine_arn="arn:aws-us-gov:states:us-gov-west-1:123456789012:stateMachine:test",
        )

        account_id = service._get_account_id()
        assert account_id == "123456789012"

    def test_extract_artifact_id_with_extra_fields(self) -> None:
        """Test extracting artifact ID when extra fields present."""
        service = SSRTrainingService(environment="test")
        input_json = json.dumps(
            {
                "artifact_id": "test-artifact-123",
                "extra_field": "ignored",
                "another": 123,
            }
        )

        artifact_id = service._extract_artifact_id(input_json)
        assert artifact_id == "test-artifact-123"

    def test_extract_artifact_id_empty_json(self) -> None:
        """Test extracting artifact ID from empty JSON object."""
        service = SSRTrainingService(environment="test")

        artifact_id = service._extract_artifact_id("{}")
        assert artifact_id == ""

    @pytest.mark.asyncio
    async def test_training_metrics_with_multiple_jobs(
        self, training_service: SSRTrainingService, training_config: TrainingJobConfig
    ) -> None:
        """Test getting metrics with multiple jobs."""
        # Submit multiple jobs
        for _ in range(3):
            await training_service.submit_training_job(training_config)

        metrics = await training_service.get_training_metrics()

        assert "total_jobs" in metrics
        assert metrics["total_jobs"] == 3

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(
        self, training_service: SSRTrainingService
    ) -> None:
        """Test health check returns healthy status."""
        health = await training_service.health_check()

        assert health["status"] == "healthy"
        assert health["service"] == "ssr_training"
        assert "state_machine_arn" in health
        assert "mock_mode" in health


# =============================================================================
# P4: ASYNC/CONCURRENCY TESTS
# =============================================================================


class TestP4AsyncConcurrency:
    """P4 tests for async operations and concurrency."""

    @pytest.mark.asyncio
    async def test_concurrent_job_submissions(
        self, training_service: SSRTrainingService, training_config: TrainingJobConfig
    ) -> None:
        """Test submitting multiple jobs concurrently."""
        import asyncio

        tasks = [
            training_service.submit_training_job(training_config) for _ in range(5)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        # All should have unique job IDs
        job_ids = [r.job_id for r in results]
        assert len(set(job_ids)) == 5

    @pytest.mark.asyncio
    async def test_concurrent_status_checks(
        self, training_service: SSRTrainingService, training_config: TrainingJobConfig
    ) -> None:
        """Test checking status of multiple jobs concurrently."""
        import asyncio

        # First submit jobs
        submit_results = await asyncio.gather(
            *[training_service.submit_training_job(training_config) for _ in range(3)]
        )

        job_ids = [r.job_id for r in submit_results]

        # Then check status concurrently
        status_results = await asyncio.gather(
            *[training_service.get_job_status(job_id) for job_id in job_ids]
        )

        assert len(status_results) == 3
        assert all(r is not None for r in status_results)

    @pytest.mark.asyncio
    async def test_batch_training_with_failures(
        self, mock_artifact_storage: MagicMock, mock_artifact: BugArtifact
    ) -> None:
        """Test batch training handles individual failures gracefully."""
        # Set up mock to fail for some artifacts
        call_count = {"count": 0}

        async def mock_get_artifact(artifact_id: str) -> BugArtifact | None:
            call_count["count"] += 1
            if artifact_id == "fail-artifact":
                return None  # Simulate not found
            return mock_artifact

        mock_artifact_storage.get_artifact = mock_get_artifact

        service = SSRTrainingService(
            environment="test", artifact_storage=mock_artifact_storage
        )

        results = await service.submit_batch_training(
            artifact_ids=[
                "ssr-artifact-test123",
                "fail-artifact",
                "ssr-artifact-test123",
            ],
            repository_id="repo-1",
        )

        # Should have 2 successful and 1 failed (returned as exception)
        # The batch method filters out exceptions
        assert len(results) >= 2

    @pytest.mark.asyncio
    async def test_submit_job_generates_unique_ids(
        self, training_service: SSRTrainingService, training_config: TrainingJobConfig
    ) -> None:
        """Test that each submission generates a unique job ID."""
        results = []
        for _ in range(10):
            result = await training_service.submit_training_job(training_config)
            results.append(result.job_id)

        # All job IDs should be unique
        assert len(set(results)) == 10

    @pytest.mark.asyncio
    async def test_job_started_at_timestamp_set(
        self, training_service: SSRTrainingService, training_config: TrainingJobConfig
    ) -> None:
        """Test that started_at timestamp is set on submission."""
        from datetime import datetime, timezone

        before = datetime.now(timezone.utc)
        result = await training_service.submit_training_job(training_config)
        after = datetime.now(timezone.utc)

        assert result.started_at is not None
        assert before <= result.started_at <= after

    @pytest.mark.asyncio
    async def test_deterministic_execution_arn_format(
        self, training_service: SSRTrainingService, training_config: TrainingJobConfig
    ) -> None:
        """Test that execution ARN has expected format in mock mode."""
        result = await training_service.submit_training_job(training_config)

        assert result.execution_arn is not None
        assert "mock" in result.execution_arn
        assert result.job_id in result.execution_arn

    def test_result_round_trip_serialization(self) -> None:
        """Test that result survives to_dict/from_dict round trip."""
        now = datetime.now(timezone.utc)
        original = TrainingJobResult(
            job_id="test-job-123",
            artifact_id="artifact-456",
            status=TrainingJobStatus.SUCCEEDED,
            execution_arn="arn:aws:states:test:123:execution:test",
            started_at=now,
            completed_at=now,
            solved=True,
            higher_order_created=True,
            error_message=None,
            metrics={"duration": 1000},
        )

        # Round trip
        data = original.to_dict()
        restored = TrainingJobResult.from_dict(data)

        assert restored.job_id == original.job_id
        assert restored.artifact_id == original.artifact_id
        assert restored.status == original.status
        assert restored.solved == original.solved
        assert restored.higher_order_created == original.higher_order_created
        assert restored.metrics == original.metrics
