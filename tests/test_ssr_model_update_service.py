"""
Tests for SSR Model Update Service.

Tests the fine-tuning pipeline, checkpoint management,
A/B testing, and rollback decisions.
"""

import platform
from datetime import datetime, timezone

import pytest

from src.services.ssr.model_update_service import (
    ABTest,
    ABTestStatus,
    DeploymentStage,
    ModelCheckpoint,
    ModelStatus,
    ModelUpdateService,
    ModelVersion,
    RollbackDecision,
)

# Run tests in forked processes for isolation
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestModelStatusEnum:
    """Tests for ModelStatus enum."""

    def test_all_statuses_defined(self):
        """Verify all expected statuses exist."""
        expected = {
            "training",
            "validating",
            "ready",
            "deployed",
            "rolled_back",
            "archived",
            "failed",
        }
        actual = {s.value for s in ModelStatus}
        assert expected == actual


class TestDeploymentStageEnum:
    """Tests for DeploymentStage enum."""

    def test_all_stages_defined(self):
        """Verify all expected deployment stages exist."""
        expected = {"canary", "shadow", "partial", "majority", "full"}
        actual = {s.value for s in DeploymentStage}
        assert expected == actual


class TestABTestStatusEnum:
    """Tests for ABTestStatus enum."""

    def test_all_statuses_defined(self):
        """Verify all expected A/B test statuses exist."""
        expected = {"pending", "running", "completed", "cancelled"}
        actual = {s.value for s in ABTestStatus}
        assert expected == actual


class TestModelCheckpoint:
    """Tests for ModelCheckpoint dataclass."""

    def test_checkpoint_creation(self):
        """Test creating a model checkpoint."""
        now = datetime.now(timezone.utc)
        checkpoint = ModelCheckpoint(
            checkpoint_id="cp-123",
            model_version="v-456",
            epoch=5,
            training_loss=0.15,
            validation_loss=0.18,
            metrics={"accuracy": 0.92},
            s3_uri="s3://bucket/cp-123.tar.gz",
            created_at=now,
        )
        assert checkpoint.checkpoint_id == "cp-123"
        assert checkpoint.epoch == 5
        assert checkpoint.training_loss == 0.15

    def test_checkpoint_serialization(self):
        """Test serialization and deserialization."""
        now = datetime.now(timezone.utc)
        checkpoint = ModelCheckpoint(
            checkpoint_id="cp-123",
            model_version="v-456",
            epoch=10,
            training_loss=0.1,
            validation_loss=0.12,
            metrics={"precision": 0.95},
            s3_uri="s3://bucket/cp.tar.gz",
            created_at=now,
        )
        data = checkpoint.to_dict()
        restored = ModelCheckpoint.from_dict(data)
        assert restored.checkpoint_id == checkpoint.checkpoint_id
        assert restored.epoch == checkpoint.epoch


class TestModelVersion:
    """Tests for ModelVersion dataclass."""

    def test_version_creation(self):
        """Test creating a model version."""
        now = datetime.now(timezone.utc)
        version = ModelVersion(
            version_id="v-123",
            base_version="v-100",
            status=ModelStatus.TRAINING,
            training_config={"epochs": 10, "batch_size": 32},
        )
        assert version.version_id == "v-123"
        assert version.base_version == "v-100"
        assert version.status == ModelStatus.TRAINING

    def test_version_serialization(self):
        """Test serialization of model version."""
        now = datetime.now(timezone.utc)
        version = ModelVersion(
            version_id="v-123",
            base_version="v-100",
            status=ModelStatus.DEPLOYED,
            training_config={"epochs": 5},
            training_data_summary={"samples": 500},
            created_at=now,
        )
        data = version.to_dict()
        assert data["version_id"] == "v-123"
        assert data["status"] == "deployed"

    def test_version_default_values(self):
        """Test default values for model version."""
        version = ModelVersion(version_id="v-1", base_version=None)
        assert version.status == ModelStatus.TRAINING
        assert version.checkpoints == []
        assert version.solve_rate == 0.0


class TestABTest:
    """Tests for ABTest dataclass."""

    def test_ab_test_creation(self):
        """Test creating an A/B test."""
        test = ABTest(
            test_id="ab-123",
            control_version="v-100",
            treatment_version="v-101",
            status=ABTestStatus.RUNNING,
            control_traffic=0.5,
            treatment_traffic=0.5,
        )
        assert test.test_id == "ab-123"
        assert test.control_traffic == 0.5
        assert test.status == ABTestStatus.RUNNING

    def test_ab_test_serialization(self):
        """Test serialization of A/B test."""
        now = datetime.now(timezone.utc)
        test = ABTest(
            test_id="ab-123",
            control_version="v-100",
            treatment_version="v-101",
            status=ABTestStatus.COMPLETED,
            control_traffic=0.5,
            treatment_traffic=0.5,
            control_metrics={"solve_rate": 0.7},
            treatment_metrics={"solve_rate": 0.8},
            started_at=now,
        )
        data = test.to_dict()
        assert data["test_id"] == "ab-123"
        assert data["status"] == "completed"


class TestRollbackDecision:
    """Tests for RollbackDecision dataclass."""

    def test_rollback_decision_creation(self):
        """Test creating a rollback decision."""
        decision = RollbackDecision(
            should_rollback=True,
            reason="Success rate dropped below threshold",
            metrics_comparison={"solve_rate": (0.65, 0.75)},
            target_version="v-100",
        )
        assert decision.should_rollback is True
        assert decision.target_version == "v-100"

    def test_rollback_decision_no_rollback(self):
        """Test rollback decision when not needed."""
        decision = RollbackDecision(
            should_rollback=False,
            reason="Metrics within tolerance",
        )
        assert decision.should_rollback is False
        assert decision.target_version is None


class TestModelUpdateService:
    """Tests for ModelUpdateService."""

    @pytest.fixture
    def service(self):
        """Create a ModelUpdateService instance."""
        return ModelUpdateService()

    def test_service_initialization(self, service):
        """Test service initialization."""
        metrics = service.get_metrics()
        assert "total_versions" in metrics
        assert metrics["total_versions"] == 0

    def test_custom_initialization(self):
        """Test service with custom parameters."""
        service = ModelUpdateService(
            s3_bucket="custom-bucket",
            checkpoint_prefix="custom-prefix",
            max_checkpoints_per_version=5,
        )
        assert service.s3_bucket == "custom-bucket"
        assert service.checkpoint_prefix == "custom-prefix"
        assert service.max_checkpoints == 5

    def test_get_version_nonexistent(self, service):
        """Test getting non-existent version."""
        version = service.get_version("non-existent")
        assert version is None

    def test_list_versions_empty(self, service):
        """Test listing versions when empty."""
        versions = service.list_versions()
        assert versions == []

    def test_get_current_version_none(self, service):
        """Test getting current version when none deployed."""
        current = service.get_current_version()
        assert current is None


class TestModelUpdateEdgeCases:
    """Edge case tests for model update service."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return ModelUpdateService()

    def test_get_nonexistent_version(self, service):
        """Test getting non-existent version."""
        version = service.get_version("non-existent")
        assert version is None

    def test_list_versions_by_status(self, service):
        """Test filtering versions by status."""
        versions = service.list_versions(status=ModelStatus.DEPLOYED)
        assert versions == []
