"""
Project Aura - SSR Training Service

Orchestrates the Self-Play SWE-RL training pipeline, managing
bug injection and bug solving tasks via Step Functions.

This service provides:
- Training job submission and monitoring
- Integration with artifact storage
- Metrics collection and reporting
- Higher-order bug tracking

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.services.ssr.artifact_storage_service import ArtifactStorageService
from src.services.ssr.bug_artifact import ArtifactStatus

if TYPE_CHECKING:
    from mypy_boto3_stepfunctions.client import SFNClient

logger = logging.getLogger(__name__)

# AWS SDK imports with fallback
try:
    import boto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("Boto3 not available - using mock mode")


class TrainingJobStatus(Enum):
    """Training job status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    ABORTED = "aborted"


@dataclass
class TrainingJobConfig:
    """Configuration for a training job."""

    artifact_id: str
    repository_id: str
    max_attempts: int = 3
    timeout_minutes: int = 30
    subnet_ids: list[str] = field(default_factory=list)
    security_group_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingJobResult:
    """Result of a training job execution."""

    job_id: str
    artifact_id: str
    status: TrainingJobStatus
    execution_arn: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    solved: bool = False
    higher_order_created: bool = False
    error_message: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "job_id": self.job_id,
            "artifact_id": self.artifact_id,
            "status": self.status.value,
            "execution_arn": self.execution_arn,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "solved": self.solved,
            "higher_order_created": self.higher_order_created,
            "error_message": self.error_message,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingJobResult:
        """Create from dictionary."""
        return cls(
            job_id=data["job_id"],
            artifact_id=data["artifact_id"],
            status=TrainingJobStatus(data["status"]),
            execution_arn=data.get("execution_arn"),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            solved=data.get("solved", False),
            higher_order_created=data.get("higher_order_created", False),
            error_message=data.get("error_message"),
            metrics=data.get("metrics", {}),
        )


class SSRTrainingService:
    """
    Orchestrates SSR training jobs via Step Functions.

    Usage:
        service = SSRTrainingService(environment="dev")

        # Submit a training job
        result = await service.submit_training_job(config)

        # Check job status
        status = await service.get_job_status(job_id)

        # Get training metrics
        metrics = await service.get_training_metrics()
    """

    def __init__(
        self,
        project_name: str = "aura",
        environment: str | None = None,
        region: str | None = None,
        state_machine_arn: str | None = None,
        artifact_storage: ArtifactStorageService | None = None,
    ):
        """
        Initialize the training service.

        Args:
            project_name: Project name for resource naming
            environment: Environment (dev, qa, prod)
            region: AWS region
            state_machine_arn: Override state machine ARN
            artifact_storage: Optional artifact storage service
        """
        self.project_name = project_name
        self.environment = environment or os.environ.get("ENVIRONMENT", "dev")
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

        # State machine ARN
        self.state_machine_arn = state_machine_arn or os.environ.get(
            "SSR_STATE_MACHINE_ARN",
            f"arn:aws:states:{self.region}:000000000000:stateMachine:"
            f"{project_name}-ssr-training-workflow-{self.environment}",
        )

        # Lazy AWS client initialization
        self._sfn: SFNClient | None = None

        # Mock mode for testing
        self._use_mock = not BOTO3_AVAILABLE or self.environment == "test"
        self._mock_executions: dict[str, TrainingJobResult] = {}

        # Artifact storage
        self._artifact_storage = artifact_storage

        logger.info(
            f"SSRTrainingService initialized: state_machine={self.state_machine_arn}, "
            f"mock_mode={self._use_mock}"
        )

    # =========================================================================
    # AWS Client Properties
    # =========================================================================

    @property
    def sfn(self) -> SFNClient | None:
        """Get or create Step Functions client."""
        if self._sfn is None and BOTO3_AVAILABLE and not self._use_mock:
            try:
                self._sfn = boto3.client("stepfunctions", region_name=self.region)
            except Exception as e:
                logger.warning(f"Failed to create Step Functions client: {e}")
                self._use_mock = True
        return self._sfn

    @property
    def artifact_storage(self) -> ArtifactStorageService:
        """Get or create artifact storage service."""
        if self._artifact_storage is None:
            self._artifact_storage = ArtifactStorageService(
                project_name=self.project_name,
                environment=self.environment,
                region=self.region,
            )
        return self._artifact_storage

    # =========================================================================
    # Training Job Operations
    # =========================================================================

    async def submit_training_job(
        self,
        config: TrainingJobConfig,
    ) -> TrainingJobResult:
        """
        Submit a new training job.

        Args:
            config: Training job configuration

        Returns:
            TrainingJobResult with job ID and initial status

        Raises:
            ValueError: If artifact doesn't exist or isn't valid
        """
        # Generate job ID
        job_id = f"ssr-job-{uuid.uuid4().hex[:12]}"

        # Validate artifact exists and is valid
        artifact = await self.artifact_storage.get_artifact(config.artifact_id)
        if not artifact:
            raise ValueError(f"Artifact not found: {config.artifact_id}")

        if artifact.status != ArtifactStatus.VALID:
            raise ValueError(
                f"Artifact is not valid for training: {artifact.status.value}"
            )

        # Prepare Step Functions input
        sfn_input = {
            "training_job_id": job_id,
            "artifact_id": config.artifact_id,
            "repository_id": config.repository_id,
            "max_attempts": config.max_attempts,
            "timeout_minutes": config.timeout_minutes,
            "subnet_ids": ",".join(config.subnet_ids) if config.subnet_ids else "",
            "security_group_id": config.security_group_id,
            "metadata": config.metadata,
        }

        result = TrainingJobResult(
            job_id=job_id,
            artifact_id=config.artifact_id,
            status=TrainingJobStatus.PENDING,
            started_at=datetime.now(timezone.utc),
        )

        if self._use_mock:
            result.status = TrainingJobStatus.RUNNING
            result.execution_arn = (
                f"arn:aws:states:{self.region}:000000000000:execution:mock:{job_id}"
            )
            self._mock_executions[job_id] = result
            logger.debug(f"Submitted mock training job: {job_id}")
            return result

        if not self.sfn:
            raise RuntimeError("Step Functions client not available")

        try:
            response = self.sfn.start_execution(
                stateMachineArn=self.state_machine_arn,
                name=job_id,
                input=json.dumps(sfn_input),
            )

            result.execution_arn = response["executionArn"]
            result.status = TrainingJobStatus.RUNNING
            result.started_at = response["startDate"]

            logger.info(f"Submitted training job: {job_id}")
            return result

        except ClientError as e:
            logger.error(f"Failed to submit training job: {e}")
            result.status = TrainingJobStatus.FAILED
            result.error_message = str(e)
            return result

    async def get_job_status(self, job_id: str) -> TrainingJobResult | None:
        """
        Get status of a training job.

        Args:
            job_id: The training job ID

        Returns:
            TrainingJobResult or None if not found
        """
        if self._use_mock:
            return self._mock_executions.get(job_id)

        if not self.sfn:
            return None

        try:
            # Find execution by name
            execution_arn = (
                f"arn:aws:states:{self.region}:"
                f"{self._get_account_id()}:execution:"
                f"{self.project_name}-ssr-training-workflow-{self.environment}:{job_id}"
            )

            response = self.sfn.describe_execution(executionArn=execution_arn)

            status_map = {
                "RUNNING": TrainingJobStatus.RUNNING,
                "SUCCEEDED": TrainingJobStatus.SUCCEEDED,
                "FAILED": TrainingJobStatus.FAILED,
                "TIMED_OUT": TrainingJobStatus.TIMED_OUT,
                "ABORTED": TrainingJobStatus.ABORTED,
            }

            # Parse output if available
            solved = False
            higher_order_created = False
            if response.get("output"):
                output = json.loads(response["output"])
                solved = output.get("solved", False)
                higher_order_created = output.get("higher_order_created", False)

            return TrainingJobResult(
                job_id=job_id,
                artifact_id=self._extract_artifact_id(response.get("input", "{}")),
                status=status_map.get(response["status"], TrainingJobStatus.FAILED),
                execution_arn=execution_arn,
                started_at=response.get("startDate"),
                completed_at=response.get("stopDate"),
                solved=solved,
                higher_order_created=higher_order_created,
                error_message=response.get("error"),
            )

        except ClientError as e:
            if "ExecutionDoesNotExist" in str(e):
                return None
            logger.error(f"Failed to get job status: {e}")
            return None

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running training job.

        Args:
            job_id: The training job ID

        Returns:
            True if cancelled successfully
        """
        if self._use_mock:
            if job_id in self._mock_executions:
                self._mock_executions[job_id].status = TrainingJobStatus.ABORTED
                return True
            return False

        if not self.sfn:
            return False

        try:
            execution_arn = (
                f"arn:aws:states:{self.region}:"
                f"{self._get_account_id()}:execution:"
                f"{self.project_name}-ssr-training-workflow-{self.environment}:{job_id}"
            )

            self.sfn.stop_execution(
                executionArn=execution_arn,
                cause="Cancelled by user",
            )

            logger.info(f"Cancelled training job: {job_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to cancel job: {e}")
            return False

    async def list_jobs(
        self,
        status: TrainingJobStatus | None = None,
        limit: int = 100,
    ) -> list[TrainingJobResult]:
        """
        List training jobs.

        Args:
            status: Optional status filter
            limit: Maximum number of results

        Returns:
            List of training job results
        """
        if self._use_mock:
            results = list(self._mock_executions.values())
            if status:
                results = [r for r in results if r.status == status]
            return results[:limit]

        if not self.sfn:
            return []

        try:
            # Map status to Step Functions status filter
            sfn_status = None
            if status:
                status_map = {
                    TrainingJobStatus.RUNNING: "RUNNING",
                    TrainingJobStatus.SUCCEEDED: "SUCCEEDED",
                    TrainingJobStatus.FAILED: "FAILED",
                    TrainingJobStatus.TIMED_OUT: "TIMED_OUT",
                    TrainingJobStatus.ABORTED: "ABORTED",
                }
                sfn_status = status_map.get(status)

            params: dict[str, Any] = {
                "stateMachineArn": self.state_machine_arn,
                "maxResults": min(limit, 100),
            }
            if sfn_status:
                params["statusFilter"] = sfn_status

            response = self.sfn.list_executions(**params)

            results = []
            for execution in response.get("executions", []):
                job_id = execution["name"]
                result = await self.get_job_status(job_id)
                if result:
                    results.append(result)

            return results

        except ClientError as e:
            logger.error(f"Failed to list jobs: {e}")
            return []

    # =========================================================================
    # Batch Operations
    # =========================================================================

    async def submit_batch_training(
        self,
        artifact_ids: list[str],
        repository_id: str,
        max_concurrent: int = 10,
        **kwargs: Any,
    ) -> list[TrainingJobResult]:
        """
        Submit multiple training jobs with concurrency control.

        Args:
            artifact_ids: List of artifact IDs to train on
            repository_id: Repository ID
            max_concurrent: Maximum concurrent jobs
            **kwargs: Additional config parameters

        Returns:
            List of training job results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results: list[TrainingJobResult] = []

        async def submit_one(artifact_id: str) -> TrainingJobResult:
            async with semaphore:
                config = TrainingJobConfig(
                    artifact_id=artifact_id,
                    repository_id=repository_id,
                    **kwargs,
                )
                return await self.submit_training_job(config)

        tasks = [submit_one(aid) for aid in artifact_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results = []
        for r in results:
            if isinstance(r, TrainingJobResult):
                valid_results.append(r)
            elif isinstance(r, Exception):
                logger.error(f"Batch training error: {r}")

        return valid_results

    # =========================================================================
    # Metrics and Reporting
    # =========================================================================

    async def get_training_metrics(
        self,
        repository_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get training metrics.

        Args:
            repository_id: Optional repository filter

        Returns:
            Dictionary of training metrics
        """
        jobs = await self.list_jobs(limit=1000)

        if repository_id:
            # Filter by repository (would need to fetch artifact details)
            pass

        total = len(jobs)
        succeeded = sum(1 for j in jobs if j.status == TrainingJobStatus.SUCCEEDED)
        failed = sum(1 for j in jobs if j.status == TrainingJobStatus.FAILED)
        running = sum(1 for j in jobs if j.status == TrainingJobStatus.RUNNING)
        solved = sum(1 for j in jobs if j.solved)
        higher_order = sum(1 for j in jobs if j.higher_order_created)

        return {
            "total_jobs": total,
            "succeeded": succeeded,
            "failed": failed,
            "running": running,
            "solved_bugs": solved,
            "higher_order_bugs_created": higher_order,
            "success_rate": succeeded / total if total > 0 else 0,
            "solve_rate": solved / succeeded if succeeded > 0 else 0,
        }

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """
        Check service health.

        Returns:
            Health status dictionary
        """
        status: dict[str, Any] = {
            "service": "ssr_training",
            "status": "healthy",
            "mock_mode": self._use_mock,
            "state_machine_arn": self.state_machine_arn,
        }

        if self._use_mock:
            status["mock_executions"] = len(self._mock_executions)
            return status

        # Check Step Functions
        try:
            if self.sfn:
                self.sfn.describe_state_machine(stateMachineArn=self.state_machine_arn)
                status["step_functions_status"] = "connected"
        except Exception as e:
            status["step_functions_status"] = f"error: {e}"
            status["status"] = "degraded"

        return status

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_account_id(self) -> str:
        """Get AWS account ID from state machine ARN."""
        parts = self.state_machine_arn.split(":")
        return parts[4] if len(parts) > 4 else "000000000000"

    def _extract_artifact_id(self, input_json: str) -> str:
        """Extract artifact ID from Step Functions input."""
        try:
            data = json.loads(input_json)
            return data.get("artifact_id", "")
        except json.JSONDecodeError:
            return ""


# =============================================================================
# Factory Function
# =============================================================================


def create_training_service(
    project_name: str = "aura",
    environment: str | None = None,
    region: str | None = None,
) -> SSRTrainingService:
    """
    Factory function to create an SSRTrainingService.

    Args:
        project_name: Project name for resource naming
        environment: Environment (dev, qa, prod)
        region: AWS region

    Returns:
        Configured SSRTrainingService instance
    """
    return SSRTrainingService(
        project_name=project_name,
        environment=environment,
        region=region,
    )
