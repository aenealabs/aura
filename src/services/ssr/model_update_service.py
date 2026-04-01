"""
Project Aura - Model Update Service for Self-Play SWE-RL

Manages incremental fine-tuning, checkpoint management, and A/B testing
for model updates in the self-play training loop.

Reference: Meta FAIR "Self-play SWE-RL" (arXiv:2512.18552), Section 6

Key Features:
- Incremental fine-tuning pipeline
- Checkpoint management and versioning
- Automatic rollback on performance regression
- A/B testing infrastructure for model comparison
- Safe deployment with gradual traffic shift

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
GitHub Issue: #165
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.services.ssr.training_data_pipeline import TrainingBatch

logger = logging.getLogger(__name__)


class ModelStatus(Enum):
    """Status of a model version."""

    TRAINING = "training"
    VALIDATING = "validating"
    READY = "ready"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"
    ARCHIVED = "archived"
    FAILED = "failed"


class DeploymentStage(Enum):
    """Stages of model deployment."""

    CANARY = "canary"  # 5% traffic
    SHADOW = "shadow"  # 0% traffic, compare results
    PARTIAL = "partial"  # 25% traffic
    MAJORITY = "majority"  # 75% traffic
    FULL = "full"  # 100% traffic


class ABTestStatus(Enum):
    """Status of an A/B test."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class ModelCheckpoint:
    """A model checkpoint from training."""

    checkpoint_id: str
    model_version: str
    epoch: int
    training_loss: float
    validation_loss: float
    metrics: dict[str, float] = field(default_factory=dict)
    s3_uri: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "model_version": self.model_version,
            "epoch": self.epoch,
            "training_loss": self.training_loss,
            "validation_loss": self.validation_loss,
            "metrics": self.metrics,
            "s3_uri": self.s3_uri,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelCheckpoint:
        """Deserialize from dictionary."""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            model_version=data["model_version"],
            epoch=data["epoch"],
            training_loss=data["training_loss"],
            validation_loss=data["validation_loss"],
            metrics=data.get("metrics", {}),
            s3_uri=data.get("s3_uri", ""),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now(timezone.utc)
            ),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ModelVersion:
    """A versioned model with training history."""

    version_id: str
    base_version: str | None  # Parent version for incremental training
    status: ModelStatus = ModelStatus.TRAINING
    checkpoints: list[ModelCheckpoint] = field(default_factory=list)

    # Training configuration
    training_config: dict[str, Any] = field(default_factory=dict)
    training_data_summary: dict[str, Any] = field(default_factory=dict)

    # Performance metrics
    solve_rate: float = 0.0
    avg_attempts: float = 0.0
    difficulty_scores: dict[int, float] = field(default_factory=dict)

    # Deployment info
    deployment_stage: DeploymentStage | None = None
    traffic_percentage: float = 0.0

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deployed_at: datetime | None = None
    retired_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version_id": self.version_id,
            "base_version": self.base_version,
            "status": self.status.value,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "training_config": self.training_config,
            "training_data_summary": self.training_data_summary,
            "solve_rate": self.solve_rate,
            "avg_attempts": self.avg_attempts,
            "difficulty_scores": self.difficulty_scores,
            "deployment_stage": (
                self.deployment_stage.value if self.deployment_stage else None
            ),
            "traffic_percentage": self.traffic_percentage,
            "created_at": self.created_at.isoformat(),
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "retired_at": self.retired_at.isoformat() if self.retired_at else None,
        }


@dataclass
class ABTest:
    """A/B test comparing two model versions."""

    test_id: str
    control_version: str
    treatment_version: str
    status: ABTestStatus = ABTestStatus.PENDING

    # Traffic split
    control_traffic: float = 0.5
    treatment_traffic: float = 0.5

    # Results
    control_metrics: dict[str, float] = field(default_factory=dict)
    treatment_metrics: dict[str, float] = field(default_factory=dict)
    control_samples: int = 0
    treatment_samples: int = 0

    # Statistical significance
    p_value: float | None = None
    is_significant: bool = False
    winner: str | None = None

    # Timestamps
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "test_id": self.test_id,
            "control_version": self.control_version,
            "treatment_version": self.treatment_version,
            "status": self.status.value,
            "control_traffic": self.control_traffic,
            "treatment_traffic": self.treatment_traffic,
            "control_metrics": self.control_metrics,
            "treatment_metrics": self.treatment_metrics,
            "control_samples": self.control_samples,
            "treatment_samples": self.treatment_samples,
            "p_value": self.p_value,
            "is_significant": self.is_significant,
            "winner": self.winner,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


@dataclass
class RollbackDecision:
    """Decision on whether to rollback a model deployment."""

    should_rollback: bool
    reason: str
    metrics_comparison: dict[str, tuple[float, float]] = field(default_factory=dict)
    target_version: str | None = None


class ModelUpdateService:
    """
    Service for managing model updates and deployments.

    This service handles the lifecycle of model versions from training
    through deployment, including checkpoint management, A/B testing,
    and automatic rollback on performance regression.

    Usage:
        service = ModelUpdateService()

        # Start incremental training
        version = await service.start_training(
            training_batch=batch,
            base_version="v1.0.0"
        )

        # Save checkpoint during training
        checkpoint = await service.save_checkpoint(
            version_id=version.version_id,
            epoch=10,
            training_loss=0.5,
            validation_loss=0.55
        )

        # Validate and deploy
        if await service.validate_model(version.version_id):
            await service.deploy_model(
                version_id=version.version_id,
                stage=DeploymentStage.CANARY
            )

        # Run A/B test
        test = await service.start_ab_test(
            control_version="v1.0.0",
            treatment_version="v1.1.0"
        )
    """

    # Thresholds for automatic decisions
    MIN_SOLVE_RATE_IMPROVEMENT = 0.02  # 2% improvement required
    MAX_REGRESSION_ALLOWED = 0.05  # 5% regression triggers rollback
    MIN_SAMPLES_FOR_SIGNIFICANCE = 100
    P_VALUE_THRESHOLD = 0.05

    def __init__(
        self,
        s3_bucket: str = "aura-ssr-models",
        checkpoint_prefix: str = "checkpoints",
        max_checkpoints_per_version: int = 10,
    ):
        """
        Initialize the model update service.

        Args:
            s3_bucket: S3 bucket for model storage
            checkpoint_prefix: S3 prefix for checkpoints
            max_checkpoints_per_version: Max checkpoints to keep per version
        """
        self.s3_bucket = s3_bucket
        self.checkpoint_prefix = checkpoint_prefix
        self.max_checkpoints = max_checkpoints_per_version

        # Model registry
        self._versions: dict[str, ModelVersion] = {}
        self._current_deployed: str | None = None

        # A/B tests
        self._ab_tests: dict[str, ABTest] = {}
        self._active_ab_test: str | None = None

        # Metrics history for rollback decisions
        self._metrics_history: list[dict[str, Any]] = []

        logger.info(
            f"ModelUpdateService initialized: bucket={s3_bucket}, "
            f"max_checkpoints={max_checkpoints_per_version}"
        )

    async def start_training(
        self,
        training_batch: TrainingBatch,
        base_version: str | None = None,
        training_config: dict[str, Any] | None = None,
    ) -> ModelVersion:
        """
        Start training a new model version.

        Args:
            training_batch: Training data batch
            base_version: Base version for incremental training
            training_config: Training hyperparameters

        Returns:
            New ModelVersion
        """
        version_id = self._generate_version_id(base_version)

        version = ModelVersion(
            version_id=version_id,
            base_version=base_version,
            status=ModelStatus.TRAINING,
            training_config=training_config or self._default_training_config(),
            training_data_summary={
                "batch_id": training_batch.batch_id,
                "size": training_batch.size,
                "total_reward": training_batch.total_reward,
            },
        )

        self._versions[version_id] = version

        logger.info(
            f"Started training version {version_id} "
            f"(base: {base_version or 'none'})"
        )

        return version

    async def save_checkpoint(
        self,
        version_id: str,
        epoch: int,
        training_loss: float,
        validation_loss: float,
        metrics: dict[str, float] | None = None,
    ) -> ModelCheckpoint:
        """
        Save a training checkpoint.

        Args:
            version_id: Model version ID
            epoch: Current epoch
            training_loss: Training loss
            validation_loss: Validation loss
            metrics: Additional metrics

        Returns:
            Saved checkpoint
        """
        if version_id not in self._versions:
            raise ValueError(f"Unknown version: {version_id}")

        version = self._versions[version_id]

        checkpoint_id = f"{version_id}-epoch-{epoch}"
        s3_uri = f"s3://{self.s3_bucket}/{self.checkpoint_prefix}/{version_id}/{checkpoint_id}"

        checkpoint = ModelCheckpoint(
            checkpoint_id=checkpoint_id,
            model_version=version_id,
            epoch=epoch,
            training_loss=training_loss,
            validation_loss=validation_loss,
            metrics=metrics or {},
            s3_uri=s3_uri,
        )

        version.checkpoints.append(checkpoint)

        # Prune old checkpoints
        if len(version.checkpoints) > self.max_checkpoints:
            version.checkpoints = version.checkpoints[-self.max_checkpoints :]

        logger.debug(
            f"Saved checkpoint {checkpoint_id}: "
            f"train_loss={training_loss:.4f}, val_loss={validation_loss:.4f}"
        )

        return checkpoint

    async def validate_model(
        self,
        version_id: str,
        validation_data: list[dict[str, Any]] | None = None,
    ) -> bool:
        """
        Validate a trained model.

        Args:
            version_id: Model version ID
            validation_data: Optional validation dataset

        Returns:
            True if validation passed
        """
        if version_id not in self._versions:
            raise ValueError(f"Unknown version: {version_id}")

        version = self._versions[version_id]
        version.status = ModelStatus.VALIDATING

        # Check for minimum checkpoints
        if not version.checkpoints:
            logger.warning(f"No checkpoints for version {version_id}")
            version.status = ModelStatus.FAILED
            return False

        # Get best checkpoint (lowest validation loss)
        best_checkpoint = min(version.checkpoints, key=lambda c: c.validation_loss)

        # Simulate validation (in production, would run actual inference)
        solve_rate = self._simulate_validation(best_checkpoint)
        version.solve_rate = solve_rate

        # Compare to base version if exists
        if version.base_version and version.base_version in self._versions:
            base = self._versions[version.base_version]
            if solve_rate < base.solve_rate - self.MAX_REGRESSION_ALLOWED:
                logger.warning(
                    f"Validation failed: solve_rate {solve_rate:.3f} < "
                    f"base {base.solve_rate:.3f}"
                )
                version.status = ModelStatus.FAILED
                return False

        version.status = ModelStatus.READY
        logger.info(f"Validation passed for {version_id}: solve_rate={solve_rate:.3f}")

        return True

    async def deploy_model(
        self,
        version_id: str,
        stage: DeploymentStage = DeploymentStage.CANARY,
    ) -> bool:
        """
        Deploy a model version.

        Args:
            version_id: Model version ID
            stage: Deployment stage

        Returns:
            True if deployment successful
        """
        if version_id not in self._versions:
            raise ValueError(f"Unknown version: {version_id}")

        version = self._versions[version_id]

        if version.status != ModelStatus.READY:
            raise ValueError(f"Version {version_id} not ready for deployment")

        # Set traffic percentage based on stage
        traffic_map = {
            DeploymentStage.CANARY: 0.05,
            DeploymentStage.SHADOW: 0.0,
            DeploymentStage.PARTIAL: 0.25,
            DeploymentStage.MAJORITY: 0.75,
            DeploymentStage.FULL: 1.0,
        }

        version.deployment_stage = stage
        version.traffic_percentage = traffic_map[stage]
        version.status = ModelStatus.DEPLOYED
        version.deployed_at = datetime.now(timezone.utc)

        # Update current deployed if full deployment
        if stage == DeploymentStage.FULL:
            if self._current_deployed and self._current_deployed in self._versions:
                old = self._versions[self._current_deployed]
                old.status = ModelStatus.ARCHIVED
                old.retired_at = datetime.now(timezone.utc)

            self._current_deployed = version_id

        logger.info(
            f"Deployed {version_id} at stage {stage.value} "
            f"({version.traffic_percentage*100:.0f}% traffic)"
        )

        return True

    async def promote_deployment(self, version_id: str) -> DeploymentStage | None:
        """
        Promote a deployment to the next stage.

        Args:
            version_id: Model version ID

        Returns:
            New deployment stage, or None if already at full
        """
        if version_id not in self._versions:
            raise ValueError(f"Unknown version: {version_id}")

        version = self._versions[version_id]

        if not version.deployment_stage:
            raise ValueError(f"Version {version_id} not deployed")

        # Define promotion path
        promotion_path = [
            DeploymentStage.CANARY,
            DeploymentStage.PARTIAL,
            DeploymentStage.MAJORITY,
            DeploymentStage.FULL,
        ]

        try:
            current_idx = promotion_path.index(version.deployment_stage)
            if current_idx < len(promotion_path) - 1:
                next_stage = promotion_path[current_idx + 1]
                await self.deploy_model(version_id, next_stage)
                return next_stage
        except ValueError:
            pass

        return None

    async def check_for_rollback(
        self,
        version_id: str,
        current_metrics: dict[str, float],
    ) -> RollbackDecision:
        """
        Check if a rollback is needed based on current metrics.

        Args:
            version_id: Deployed version ID
            current_metrics: Current performance metrics

        Returns:
            RollbackDecision
        """
        if version_id not in self._versions:
            return RollbackDecision(
                should_rollback=False,
                reason="Unknown version",
            )

        version = self._versions[version_id]

        # No rollback if no base version
        if not version.base_version or version.base_version not in self._versions:
            return RollbackDecision(
                should_rollback=False,
                reason="No base version for comparison",
            )

        base = self._versions[version.base_version]

        # Compare key metrics
        comparisons = {}
        should_rollback = False
        reasons = []

        # Check solve rate regression
        current_solve_rate = current_metrics.get("solve_rate", version.solve_rate)
        if current_solve_rate < base.solve_rate - self.MAX_REGRESSION_ALLOWED:
            should_rollback = True
            reasons.append(
                f"Solve rate regression: {current_solve_rate:.3f} vs {base.solve_rate:.3f}"
            )
        comparisons["solve_rate"] = (current_solve_rate, base.solve_rate)

        # Check error rate
        current_error_rate = current_metrics.get("error_rate", 0)
        base_error_rate = base.training_data_summary.get("error_rate", 0)
        if current_error_rate > base_error_rate + 0.1:
            should_rollback = True
            reasons.append(f"Error rate spike: {current_error_rate:.3f}")
        comparisons["error_rate"] = (current_error_rate, base_error_rate)

        return RollbackDecision(
            should_rollback=should_rollback,
            reason="; ".join(reasons) if reasons else "Metrics within tolerance",
            metrics_comparison=comparisons,
            target_version=version.base_version if should_rollback else None,
        )

    async def rollback(
        self,
        from_version: str,
        to_version: str,
        reason: str,
    ) -> bool:
        """
        Rollback from one version to another.

        Args:
            from_version: Current version to rollback
            to_version: Target version to restore
            reason: Reason for rollback

        Returns:
            True if rollback successful
        """
        if from_version not in self._versions or to_version not in self._versions:
            raise ValueError("Invalid version IDs")

        current = self._versions[from_version]
        target = self._versions[to_version]

        # Mark current as rolled back
        current.status = ModelStatus.ROLLED_BACK
        current.retired_at = datetime.now(timezone.utc)

        # Restore target
        target.status = ModelStatus.DEPLOYED
        target.deployment_stage = DeploymentStage.FULL
        target.traffic_percentage = 1.0

        self._current_deployed = to_version

        logger.warning(f"Rollback: {from_version} -> {to_version}, reason: {reason}")

        return True

    async def start_ab_test(
        self,
        control_version: str,
        treatment_version: str,
        traffic_split: tuple[float, float] = (0.5, 0.5),
    ) -> ABTest:
        """
        Start an A/B test between two versions.

        Args:
            control_version: Control (baseline) version
            treatment_version: Treatment (new) version
            traffic_split: (control_traffic, treatment_traffic)

        Returns:
            ABTest instance
        """
        if self._active_ab_test:
            raise ValueError("An A/B test is already running")

        test_id = f"ab-{uuid.uuid4().hex[:8]}"

        test = ABTest(
            test_id=test_id,
            control_version=control_version,
            treatment_version=treatment_version,
            control_traffic=traffic_split[0],
            treatment_traffic=traffic_split[1],
            status=ABTestStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        self._ab_tests[test_id] = test
        self._active_ab_test = test_id

        logger.info(
            f"Started A/B test {test_id}: " f"{control_version} vs {treatment_version}"
        )

        return test

    async def record_ab_result(
        self,
        test_id: str,
        is_treatment: bool,
        metrics: dict[str, float],
    ) -> None:
        """
        Record a result for an A/B test.

        Args:
            test_id: A/B test ID
            is_treatment: Whether this is for treatment group
            metrics: Metrics for this sample
        """
        if test_id not in self._ab_tests:
            return

        test = self._ab_tests[test_id]

        if is_treatment:
            test.treatment_samples += 1
            for key, value in metrics.items():
                current = test.treatment_metrics.get(key, 0)
                # Running average
                n = test.treatment_samples
                test.treatment_metrics[key] = current + (value - current) / n
        else:
            test.control_samples += 1
            for key, value in metrics.items():
                current = test.control_metrics.get(key, 0)
                n = test.control_samples
                test.control_metrics[key] = current + (value - current) / n

    async def analyze_ab_test(self, test_id: str) -> ABTest:
        """
        Analyze an A/B test for statistical significance.

        Args:
            test_id: A/B test ID

        Returns:
            Updated ABTest with analysis
        """
        if test_id not in self._ab_tests:
            raise ValueError(f"Unknown test: {test_id}")

        test = self._ab_tests[test_id]

        # Need minimum samples
        total_samples = test.control_samples + test.treatment_samples
        if total_samples < self.MIN_SAMPLES_FOR_SIGNIFICANCE:
            return test

        # Simple comparison (in production, use proper statistical tests)
        control_rate = test.control_metrics.get("solve_rate", 0)
        treatment_rate = test.treatment_metrics.get("solve_rate", 0)

        # Simplified significance calculation
        diff = treatment_rate - control_rate
        if abs(diff) > self.MIN_SOLVE_RATE_IMPROVEMENT:
            test.is_significant = True
            test.winner = test.treatment_version if diff > 0 else test.control_version
            # Simulated p-value based on sample size and effect size
            test.p_value = max(0.001, 0.1 / (total_samples / 100))

        return test

    async def complete_ab_test(self, test_id: str) -> str | None:
        """
        Complete an A/B test and return the winner.

        Args:
            test_id: A/B test ID

        Returns:
            Winner version ID, or None if no winner
        """
        test = await self.analyze_ab_test(test_id)

        test.status = ABTestStatus.COMPLETED
        test.completed_at = datetime.now(timezone.utc)

        if self._active_ab_test == test_id:
            self._active_ab_test = None

        logger.info(
            f"Completed A/B test {test_id}: "
            f"winner={test.winner}, significant={test.is_significant}"
        )

        return test.winner

    def get_current_version(self) -> str | None:
        """Get the current deployed version ID."""
        return self._current_deployed

    def get_version(self, version_id: str) -> ModelVersion | None:
        """Get a model version by ID."""
        return self._versions.get(version_id)

    def list_versions(
        self,
        status: ModelStatus | None = None,
    ) -> list[ModelVersion]:
        """List model versions, optionally filtered by status."""
        versions = list(self._versions.values())
        if status:
            versions = [v for v in versions if v.status == status]
        return sorted(versions, key=lambda v: v.created_at, reverse=True)

    def _generate_version_id(self, base_version: str | None) -> str:
        """Generate a new version ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        if base_version:
            # Increment from base
            parts = base_version.split(".")
            if len(parts) >= 2:
                try:
                    minor = int(parts[1]) + 1
                    return f"{parts[0]}.{minor}.0"
                except ValueError:
                    pass

        return f"v1.{timestamp[:8]}.0"

    def _default_training_config(self) -> dict[str, Any]:
        """Get default training configuration."""
        return {
            "learning_rate": 1e-5,
            "batch_size": 32,
            "epochs": 3,
            "warmup_steps": 100,
            "weight_decay": 0.01,
            "gradient_accumulation_steps": 4,
        }

    def _simulate_validation(self, checkpoint: ModelCheckpoint) -> float:
        """Simulate validation (placeholder for actual model inference)."""
        # In production, this would run actual inference on validation set
        # For now, estimate based on validation loss
        base_rate = 0.5
        loss_factor = max(0, 1 - checkpoint.validation_loss)
        return min(0.95, base_rate + loss_factor * 0.4)

    def get_metrics(self) -> dict[str, Any]:
        """Get service metrics."""
        status_counts = {}
        for version in self._versions.values():
            status = version.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_versions": len(self._versions),
            "current_deployed": self._current_deployed,
            "status_distribution": status_counts,
            "active_ab_test": self._active_ab_test,
            "total_ab_tests": len(self._ab_tests),
            "total_checkpoints": sum(
                len(v.checkpoints) for v in self._versions.values()
            ),
        }
