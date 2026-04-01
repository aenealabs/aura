"""Tests for Environment Validator baseline manager (ADR-062 Phase 2)."""

import json
from datetime import datetime

from src.services.env_validator.baseline_manager import (
    Baseline,
    DriftHistory,
    MockBaselineManager,
)


class TestBaseline:
    """Tests for Baseline dataclass."""

    def test_baseline_pk_format(self):
        """Test partition key format."""
        baseline = Baseline(
            environment="qa",
            resource_type="ConfigMap",
            resource_name="aura-api-config",
            namespace="default",
            content={"data": {"ENVIRONMENT": "qa"}},
            content_hash="abc123",
            validated_at=datetime.utcnow(),
            validation_run_id="run-001",
            created_by="test",
        )

        assert baseline.pk == "ENV#qa"

    def test_baseline_sk_format(self):
        """Test sort key format."""
        baseline = Baseline(
            environment="qa",
            resource_type="ConfigMap",
            resource_name="aura-api-config",
            namespace="aura-system",
            content={},
            content_hash="abc123",
            validated_at=datetime.utcnow(),
            validation_run_id="run-001",
            created_by="test",
        )

        assert baseline.sk == "BASELINE#ConfigMap#aura-system#aura-api-config"

    def test_baseline_to_item(self):
        """Test DynamoDB item conversion."""
        now = datetime.utcnow()
        baseline = Baseline(
            environment="qa",
            resource_type="Deployment",
            resource_name="aura-api",
            namespace="default",
            content={"spec": {"replicas": 3}},
            content_hash="def456",
            validated_at=now,
            validation_run_id="run-002",
            created_by="system",
        )

        item = baseline.to_item()

        assert item["PK"]["S"] == "ENV#qa"
        assert item["SK"]["S"] == "BASELINE#Deployment#default#aura-api"
        assert item["environment"]["S"] == "qa"
        assert item["resource_type"]["S"] == "Deployment"
        assert item["content"]["S"] == json.dumps({"spec": {"replicas": 3}})
        assert item["content_hash"]["S"] == "def456"
        assert item["gsi1pk"]["S"] == "TYPE#Deployment"
        assert item["gsi1sk"]["S"] == "ENV#qa#default#aura-api"

    def test_baseline_from_item(self):
        """Test creating Baseline from DynamoDB item."""
        now = datetime.utcnow()
        item = {
            "PK": {"S": "ENV#qa"},
            "SK": {"S": "BASELINE#ConfigMap#default#test-config"},
            "environment": {"S": "qa"},
            "resource_type": {"S": "ConfigMap"},
            "resource_name": {"S": "test-config"},
            "namespace": {"S": "default"},
            "content": {"S": '{"data": {"key": "value"}}'},
            "content_hash": {"S": "hash123"},
            "validated_at": {"S": now.isoformat()},
            "validation_run_id": {"S": "run-003"},
            "created_by": {"S": "user"},
        }

        baseline = Baseline.from_item(item)

        assert baseline.environment == "qa"
        assert baseline.resource_type == "ConfigMap"
        assert baseline.resource_name == "test-config"
        assert baseline.namespace == "default"
        assert baseline.content == {"data": {"key": "value"}}
        assert baseline.content_hash == "hash123"
        assert baseline.created_by == "user"


class TestDriftHistory:
    """Tests for DriftHistory dataclass."""

    def test_drift_history_pk_format(self):
        """Test partition key format."""
        history = DriftHistory(
            environment="qa",
            event_id="evt-001",
            detected_at=datetime.utcnow(),
            resource_type="ConfigMap",
            resource_name="aura-config",
            namespace="default",
            field_path="data.ENVIRONMENT",
            baseline_value="qa",
            current_value="dev",
            severity="critical",
            resolved=False,
            resolved_at=None,
        )

        assert history.pk == "ENV#qa"

    def test_drift_history_sk_format(self):
        """Test sort key format includes timestamp and event ID."""
        now = datetime.utcnow()
        history = DriftHistory(
            environment="qa",
            event_id="evt-123",
            detected_at=now,
            resource_type="ConfigMap",
            resource_name="test",
            namespace="default",
            field_path="data.KEY",
            baseline_value="old",
            current_value="new",
            severity="warning",
            resolved=False,
            resolved_at=None,
        )

        assert history.sk == f"DRIFT#{now.isoformat()}#evt-123"

    def test_drift_history_to_item_unresolved(self):
        """Test DynamoDB item conversion for unresolved drift."""
        now = datetime.utcnow()
        history = DriftHistory(
            environment="dev",
            event_id="evt-456",
            detected_at=now,
            resource_type="Deployment",
            resource_name="aura-api",
            namespace="aura-system",
            field_path="spec.template.spec.containers.0.image",
            baseline_value="ecr/image:v1",
            current_value="ecr/image:v2",
            severity="critical",
            resolved=False,
            resolved_at=None,
        )

        item = history.to_item()

        assert item["PK"]["S"] == "ENV#dev"
        assert item["environment"]["S"] == "dev"
        assert item["event_id"]["S"] == "evt-456"
        assert item["field_path"]["S"] == "spec.template.spec.containers.0.image"
        assert item["severity"]["S"] == "critical"
        assert item["resolved"]["BOOL"] is False
        assert "resolved_at" not in item
        assert item["gsi1pk"]["S"] == "SEVERITY#critical"

    def test_drift_history_to_item_resolved(self):
        """Test DynamoDB item conversion includes resolved_at when present."""
        now = datetime.utcnow()
        resolved_time = datetime.utcnow()
        history = DriftHistory(
            environment="qa",
            event_id="evt-789",
            detected_at=now,
            resource_type="ConfigMap",
            resource_name="test",
            namespace="default",
            field_path="data.KEY",
            baseline_value="old",
            current_value="new",
            severity="info",
            resolved=True,
            resolved_at=resolved_time,
        )

        item = history.to_item()

        assert item["resolved"]["BOOL"] is True
        assert item["resolved_at"]["S"] == resolved_time.isoformat()


class TestMockBaselineManager:
    """Tests for MockBaselineManager."""

    def test_mock_manager_save_and_get_baseline(self):
        """Test saving and retrieving a baseline using mock manager."""
        manager = MockBaselineManager("qa")

        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
  namespace: default
data:
  ENVIRONMENT: qa
"""

        baselines = manager.save_baseline(manifest, "run-001", "test-user")

        assert len(baselines) == 1
        assert baselines[0].resource_type == "ConfigMap"
        assert baselines[0].resource_name == "test-config"

        # Retrieve the baseline
        retrieved = manager.get_baseline("qa", "ConfigMap", "test-config", "default")

        assert retrieved is not None
        assert retrieved["data"]["ENVIRONMENT"] == "qa"

    def test_mock_manager_list_baselines(self):
        """Test listing all baselines for an environment."""
        manager = MockBaselineManager("qa")

        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: config-one
  namespace: default
data:
  KEY: value1
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: config-two
  namespace: default
data:
  KEY: value2
"""

        manager.save_baseline(manifest, "run-001")

        baselines = manager.list_baselines("qa")

        assert len(baselines) == 2
        names = {b.resource_name for b in baselines}
        assert "config-one" in names
        assert "config-two" in names

    def test_mock_manager_list_baselines_by_type(self):
        """Test filtering baselines by resource type."""
        manager = MockBaselineManager("dev")

        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
  namespace: default
data:
  KEY: value
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-deploy
  namespace: default
spec:
  replicas: 1
"""

        manager.save_baseline(manifest, "run-002")

        configmaps = manager.list_baselines("dev", resource_type="ConfigMap")
        deployments = manager.list_baselines("dev", resource_type="Deployment")

        assert len(configmaps) == 1
        assert configmaps[0].resource_name == "test-config"
        assert len(deployments) == 1
        assert deployments[0].resource_name == "test-deploy"

    def test_mock_manager_delete_baseline(self):
        """Test deleting a baseline."""
        manager = MockBaselineManager("qa")

        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: to-delete
  namespace: default
data:
  KEY: value
"""

        manager.save_baseline(manifest, "run-003")

        # Verify it exists
        assert (
            manager.get_baseline("qa", "ConfigMap", "to-delete", "default") is not None
        )

        # Delete it
        result = manager.delete_baseline("qa", "ConfigMap", "to-delete", "default")
        assert result is True

        # Verify it's gone
        assert manager.get_baseline("qa", "ConfigMap", "to-delete", "default") is None

    def test_mock_manager_delete_nonexistent_baseline(self):
        """Test deleting a baseline that doesn't exist."""
        manager = MockBaselineManager("qa")

        result = manager.delete_baseline("qa", "ConfigMap", "nonexistent", "default")
        assert result is False

    def test_mock_manager_add_mock_baseline(self):
        """Test adding a mock baseline directly."""
        manager = MockBaselineManager("staging")

        content = {"data": {"NEPTUNE_ENDPOINT": "neptune.staging.local"}}
        manager.add_mock_baseline("ConfigMap", "neptune-config", "aura-system", content)

        retrieved = manager.get_baseline(
            "staging", "ConfigMap", "neptune-config", "aura-system"
        )

        assert retrieved is not None
        assert retrieved["data"]["NEPTUNE_ENDPOINT"] == "neptune.staging.local"

    def test_mock_manager_get_nonexistent_baseline(self):
        """Test getting a baseline that doesn't exist returns None."""
        manager = MockBaselineManager("qa")

        result = manager.get_baseline("qa", "ConfigMap", "nonexistent", "default")

        assert result is None

    def test_mock_manager_save_invalid_yaml(self):
        """Test saving invalid YAML returns empty list."""
        manager = MockBaselineManager("qa")

        baselines = manager.save_baseline("invalid: yaml: content: [", "run-004")

        assert len(baselines) == 0

    def test_mock_manager_content_hash_computed(self):
        """Test that content hash is computed for each baseline."""
        manager = MockBaselineManager("qa")

        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: hash-test
  namespace: default
data:
  KEY: value
"""

        baselines = manager.save_baseline(manifest, "run-005")

        assert len(baselines) == 1
        assert baselines[0].content_hash is not None
        assert len(baselines[0].content_hash) == 16  # SHA256[:16]


class TestBaselineManagerDriftHistory:
    """Tests for drift history in BaselineManager."""

    def test_save_drift_event(self):
        """Test saving a drift event."""
        from src.services.env_validator.drift_detector import DriftEvent
        from src.services.env_validator.models import Severity

        manager = MockBaselineManager("qa")

        event = DriftEvent(
            event_id="drift-001",
            resource_type="ConfigMap",
            resource_name="aura-api-config",
            namespace="default",
            field_path="data.ENVIRONMENT",
            baseline_value="qa",
            current_value="dev",
            detected_at=datetime.utcnow(),
            severity=Severity.CRITICAL,
            environment="qa",
            baseline_hash="abc123",
            current_hash="def456",
        )

        result = manager.save_drift_event(event)

        assert result is True

    def test_get_unresolved_drift(self):
        """Test retrieving unresolved drift events."""
        from src.services.env_validator.drift_detector import DriftEvent
        from src.services.env_validator.models import Severity

        manager = MockBaselineManager("qa")

        # Save a drift event
        event = DriftEvent(
            event_id="drift-002",
            resource_type="Deployment",
            resource_name="aura-api",
            namespace="aura-system",
            field_path="spec.template.spec.containers.0.image",
            baseline_value="old:v1",
            current_value="new:v2",
            detected_at=datetime.utcnow(),
            severity=Severity.WARNING,
            environment="qa",
            baseline_hash="hash1",
            current_hash="hash2",
        )
        manager.save_drift_event(event)

        # Get unresolved drift
        unresolved = manager.get_unresolved_drift("qa")

        assert len(unresolved) == 1
        assert unresolved[0].event_id == "drift-002"
        assert unresolved[0].resolved is False


class TestBaselineManagerMultiDocument:
    """Tests for handling multi-document YAML manifests."""

    def test_save_multi_document_manifest(self):
        """Test saving a manifest with multiple YAML documents."""
        manager = MockBaselineManager("qa")

        manifest = """
apiVersion: v1
kind: Namespace
metadata:
  name: aura-system
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config
  namespace: aura-system
data:
  ENVIRONMENT: qa
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aura-api
  namespace: aura-system
spec:
  replicas: 3
"""

        baselines = manager.save_baseline(manifest, "run-multi")

        assert len(baselines) == 3

        kinds = {b.resource_type for b in baselines}
        assert "Namespace" in kinds
        assert "ConfigMap" in kinds
        assert "Deployment" in kinds

    def test_save_manifest_with_empty_documents(self):
        """Test saving a manifest that has empty documents (---) is handled."""
        manager = MockBaselineManager("qa")

        manifest = """
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: only-config
  namespace: default
data:
  KEY: value
---
"""

        baselines = manager.save_baseline(manifest, "run-empty-docs")

        assert len(baselines) == 1
        assert baselines[0].resource_name == "only-config"
