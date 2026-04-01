"""Tests for Environment Validator drift detector (ADR-062 Phase 2)."""

from src.services.env_validator.baseline_manager import MockBaselineManager
from src.services.env_validator.drift_detector import (
    DriftDetector,
    DriftEvent,
    DriftReport,
)
from src.services.env_validator.models import Severity

from .conftest import TEST_DEV_ACCOUNT_ID, TEST_QA_ACCOUNT_ID

# Note: clear_cache fixture moved to conftest.py (setup_test_environment)


class TestDriftEvent:
    """Tests for DriftEvent dataclass."""

    def test_drift_event_to_dict(self):
        """Test DriftEvent serialization to dict."""
        from datetime import datetime

        now = datetime.utcnow()
        event = DriftEvent(
            event_id="evt-001",
            resource_type="ConfigMap",
            resource_name="aura-config",
            namespace="default",
            field_path="data.ENVIRONMENT",
            baseline_value="qa",
            current_value="dev",
            detected_at=now,
            severity=Severity.CRITICAL,
            environment="qa",
            baseline_hash="abc123",
            current_hash="def456",
        )

        result = event.to_dict()

        assert result["event_id"] == "evt-001"
        assert result["resource_type"] == "ConfigMap"
        assert result["resource_name"] == "aura-config"
        assert result["namespace"] == "default"
        assert result["field_path"] == "data.ENVIRONMENT"
        assert result["baseline_value"] == "qa"
        assert result["current_value"] == "dev"
        assert result["severity"] == "critical"
        assert result["environment"] == "qa"
        assert result["detected_at"] == now.isoformat()


class TestDriftReport:
    """Tests for DriftReport dataclass."""

    def test_drift_report_has_drift(self):
        """Test has_drift property."""
        from datetime import datetime

        # Report with no drift events
        report_no_drift = DriftReport(
            run_id="run-001",
            environment="qa",
            timestamp=datetime.utcnow(),
            resources_checked=5,
            drift_events=[],
            validation_run=None,
        )
        assert report_no_drift.has_drift is False

        # Report with drift events
        event = DriftEvent(
            event_id="evt-001",
            resource_type="ConfigMap",
            resource_name="test",
            namespace="default",
            field_path="data.KEY",
            baseline_value="old",
            current_value="new",
            detected_at=datetime.utcnow(),
            severity=Severity.WARNING,
            environment="qa",
            baseline_hash="a",
            current_hash="b",
        )
        report_with_drift = DriftReport(
            run_id="run-002",
            environment="qa",
            timestamp=datetime.utcnow(),
            resources_checked=5,
            drift_events=[event],
            validation_run=None,
        )
        assert report_with_drift.has_drift is True

    def test_drift_report_critical_drift_count(self):
        """Test critical_drift_count property."""
        from datetime import datetime

        events = [
            DriftEvent(
                event_id="evt-001",
                resource_type="ConfigMap",
                resource_name="test1",
                namespace="default",
                field_path="data.NEPTUNE_ENDPOINT",
                baseline_value="old",
                current_value="new",
                detected_at=datetime.utcnow(),
                severity=Severity.CRITICAL,
                environment="qa",
                baseline_hash="a",
                current_hash="b",
            ),
            DriftEvent(
                event_id="evt-002",
                resource_type="ConfigMap",
                resource_name="test2",
                namespace="default",
                field_path="data.ENVIRONMENT",
                baseline_value="qa",
                current_value="dev",
                detected_at=datetime.utcnow(),
                severity=Severity.WARNING,
                environment="qa",
                baseline_hash="c",
                current_hash="d",
            ),
            DriftEvent(
                event_id="evt-003",
                resource_type="Deployment",
                resource_name="api",
                namespace="default",
                field_path="spec.template.spec.containers.0.image",
                baseline_value="img:v1",
                current_value="img:v2",
                detected_at=datetime.utcnow(),
                severity=Severity.CRITICAL,
                environment="qa",
                baseline_hash="e",
                current_hash="f",
            ),
        ]

        report = DriftReport(
            run_id="run-003",
            environment="qa",
            timestamp=datetime.utcnow(),
            resources_checked=3,
            drift_events=events,
            validation_run=None,
        )

        assert report.critical_drift_count == 2

    def test_drift_report_to_dict(self):
        """Test DriftReport serialization to dict."""
        from datetime import datetime

        now = datetime.utcnow()
        report = DriftReport(
            run_id="run-004",
            environment="qa",
            timestamp=now,
            resources_checked=10,
            drift_events=[],
            validation_run=None,
        )

        result = report.to_dict()

        assert result["run_id"] == "run-004"
        assert result["environment"] == "qa"
        assert result["timestamp"] == now.isoformat()
        assert result["resources_checked"] == 10
        assert result["has_drift"] is False
        assert result["critical_drift_count"] == 0
        assert result["drift_events"] == []


class TestDriftDetector:
    """Tests for DriftDetector class."""

    def test_detect_drift_no_baseline(self):
        """Test drift detection when no baseline exists (should skip)."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        current_manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: new-config
  namespace: default
data:
  ENVIRONMENT: qa
"""

        report = detector.detect_drift(current_manifest)

        assert report.resources_checked == 1
        assert len(report.drift_events) == 0  # No baseline = no drift detected

    def test_detect_drift_no_changes(self):
        """Test drift detection when current matches baseline."""
        manager = MockBaselineManager("qa")

        # Set up baseline
        baseline_manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config
  namespace: default
  labels:
    environment: qa
    app: aura
data:
  ENVIRONMENT: qa
  NEPTUNE_ENDPOINT: neptune.qa.local
"""
        manager.save_baseline(baseline_manifest, "baseline-run")

        # Run drift detection with same manifest
        detector = DriftDetector("qa", manager)
        report = detector.detect_drift(baseline_manifest)

        assert report.resources_checked == 1
        assert len(report.drift_events) == 0
        assert report.has_drift is False

    def test_detect_drift_environment_changed(self):
        """Test drift detection when ENVIRONMENT value changes."""
        manager = MockBaselineManager("qa")

        # Set up baseline
        baseline_manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config
  namespace: default
data:
  ENVIRONMENT: qa
"""
        manager.save_baseline(baseline_manifest, "baseline-run")

        # Current state with drift
        current_manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config
  namespace: default
data:
  ENVIRONMENT: dev
"""

        detector = DriftDetector("qa", manager)
        report = detector.detect_drift(current_manifest)

        assert report.has_drift is True
        assert len(report.drift_events) >= 1

        env_drift = [e for e in report.drift_events if "ENVIRONMENT" in e.field_path]
        assert len(env_drift) == 1
        assert env_drift[0].baseline_value == "qa"
        assert env_drift[0].current_value == "dev"
        assert env_drift[0].severity == Severity.WARNING

    def test_detect_drift_neptune_endpoint_changed(self):
        """Test drift detection for Neptune endpoint (critical)."""
        manager = MockBaselineManager("qa")

        baseline_manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config
  namespace: default
data:
  NEPTUNE_ENDPOINT: neptune.qa.local:8182
"""
        manager.save_baseline(baseline_manifest, "baseline-run")

        current_manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config
  namespace: default
data:
  NEPTUNE_ENDPOINT: neptune.dev.local:8182
"""

        detector = DriftDetector("qa", manager)
        report = detector.detect_drift(current_manifest)

        assert report.has_drift is True
        neptune_drift = [
            e for e in report.drift_events if "NEPTUNE_ENDPOINT" in e.field_path
        ]
        assert len(neptune_drift) == 1
        assert neptune_drift[0].severity == Severity.CRITICAL

    def test_detect_drift_container_image_changed(self):
        """Test drift detection for container image (critical)."""
        manager = MockBaselineManager("qa")

        baseline_manifest = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aura-api
  namespace: default
spec:
  template:
    spec:
      containers:
        - name: api
          image: {TEST_QA_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/aura-api:v1.0.0
"""
        manager.save_baseline(baseline_manifest, "baseline-run")

        current_manifest = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aura-api
  namespace: default
spec:
  template:
    spec:
      containers:
        - name: api
          image: {TEST_DEV_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/aura-api:v1.0.0
"""

        detector = DriftDetector("qa", manager)
        report = detector.detect_drift(current_manifest)

        assert report.has_drift is True
        image_drift = [e for e in report.drift_events if "image" in e.field_path]
        assert len(image_drift) == 1
        assert image_drift[0].severity == Severity.CRITICAL

    def test_detect_drift_irsa_role_changed(self):
        """Test drift detection for IRSA role annotation (critical)."""
        manager = MockBaselineManager("qa")

        baseline_manifest = f"""
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aura-api
  namespace: default
  labels:
    app: aura-api
    environment: qa
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::{TEST_QA_ACCOUNT_ID}:role/aura-api-irsa-qa
"""
        manager.save_baseline(baseline_manifest, "baseline-run")

        current_manifest = f"""
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aura-api
  namespace: default
  labels:
    app: aura-api
    environment: qa
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::{TEST_DEV_ACCOUNT_ID}:role/aura-api-irsa-dev
"""

        detector = DriftDetector("qa", manager)
        report = detector.detect_drift(current_manifest)

        assert report.has_drift is True
        irsa_drift = [e for e in report.drift_events if "role-arn" in e.field_path]
        assert len(irsa_drift) == 1
        assert irsa_drift[0].severity == Severity.CRITICAL

    def test_detect_drift_invalid_yaml(self):
        """Test drift detection with invalid YAML."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        report = detector.detect_drift("invalid: yaml: [")

        assert report.resources_checked == 0
        assert len(report.drift_events) == 0

    def test_detect_drift_multiple_resources(self):
        """Test drift detection across multiple resources."""
        manager = MockBaselineManager("qa")

        baseline_manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: config-one
  namespace: default
data:
  ENVIRONMENT: qa
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: config-two
  namespace: default
data:
  NEPTUNE_ENDPOINT: neptune.qa.local
"""
        manager.save_baseline(baseline_manifest, "baseline-run")

        # Both configs have drift
        current_manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: config-one
  namespace: default
data:
  ENVIRONMENT: dev
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: config-two
  namespace: default
data:
  NEPTUNE_ENDPOINT: neptune.dev.local
"""

        detector = DriftDetector("qa", manager)
        report = detector.detect_drift(current_manifest)

        assert report.resources_checked == 2
        assert report.has_drift is True
        assert len(report.drift_events) >= 2

    def test_detect_drift_includes_validation_run(self):
        """Test that drift detection includes validation run results."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
  namespace: default
data:
  ENVIRONMENT: qa
"""

        report = detector.detect_drift(manifest)

        assert report.validation_run is not None
        assert report.validation_run.environment == "qa"


class TestDriftDetectorFieldPaths:
    """Tests for nested field path extraction."""

    def test_get_nested_value_simple(self):
        """Test getting a simple nested value."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        obj = {"data": {"ENVIRONMENT": "qa"}}
        value = detector._get_nested_value(obj, "data.ENVIRONMENT")

        assert value == "qa"

    def test_get_nested_value_array_index(self):
        """Test getting a value from an array by index."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        obj = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {"name": "main", "image": "my-image:v1"},
                            {"name": "sidecar", "image": "sidecar:v1"},
                        ]
                    }
                }
            }
        }

        value = detector._get_nested_value(obj, "spec.template.spec.containers.0.image")
        assert value == "my-image:v1"

        value = detector._get_nested_value(obj, "spec.template.spec.containers.1.name")
        assert value == "sidecar"

    def test_get_nested_value_missing_key(self):
        """Test getting a value for a missing key returns None."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        obj = {"data": {"KEY": "value"}}
        value = detector._get_nested_value(obj, "data.MISSING")

        assert value is None

    def test_get_nested_value_array_out_of_bounds(self):
        """Test getting array value out of bounds returns None."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        obj = {"items": ["a", "b"]}
        value = detector._get_nested_value(obj, "items.5")

        assert value is None

    def test_get_nested_value_bracket_notation(self):
        """Test getting value using bracket notation for keys with dots."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        obj = {
            "metadata": {
                "annotations": {
                    "eks.amazonaws.com/role-arn": "arn:aws:iam::123456789:role/my-role"
                }
            }
        }

        value = detector._get_nested_value(
            obj, "metadata.annotations[eks.amazonaws.com/role-arn]"
        )
        assert value == "arn:aws:iam::123456789:role/my-role"

    def test_get_nested_value_mixed_bracket_and_dot(self):
        """Test getting value with mixed bracket and dot notation."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        obj = {
            "spec": {
                "containers": [{"name": "main", "env": {"my.dotted.key": "value123"}}]
            }
        }

        value = detector._get_nested_value(obj, "spec.containers.0.env[my.dotted.key]")
        assert value == "value123"


class TestDriftDetectorSeverity:
    """Tests for drift severity determination."""

    def test_severity_critical_for_endpoint(self):
        """Test that endpoint drift is critical."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        severity = detector._determine_drift_severity(
            "ConfigMap", "data.NEPTUNE_ENDPOINT"
        )
        assert severity == Severity.CRITICAL

        severity = detector._determine_drift_severity(
            "ConfigMap", "data.OPENSEARCH_ENDPOINT"
        )
        assert severity == Severity.CRITICAL

    def test_severity_critical_for_table_name(self):
        """Test that table name drift is critical."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        severity = detector._determine_drift_severity(
            "ConfigMap", "data.JOBS_TABLE_NAME"
        )
        assert severity == Severity.CRITICAL

    def test_severity_critical_for_sns(self):
        """Test that SNS ARN drift is critical."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        severity = detector._determine_drift_severity("ConfigMap", "data.SNS_TOPIC_ARN")
        assert severity == Severity.CRITICAL

    def test_severity_critical_for_image(self):
        """Test that container image drift is critical."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        severity = detector._determine_drift_severity(
            "Deployment", "spec.template.spec.containers.0.image"
        )
        assert severity == Severity.CRITICAL

    def test_severity_critical_for_irsa(self):
        """Test that IRSA role drift is critical."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        severity = detector._determine_drift_severity(
            "ServiceAccount", "metadata.annotations.eks.amazonaws.com/role-arn"
        )
        assert severity == Severity.CRITICAL

    def test_severity_warning_for_environment(self):
        """Test that ENVIRONMENT variable drift is warning."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        severity = detector._determine_drift_severity("ConfigMap", "data.ENVIRONMENT")
        assert severity == Severity.WARNING

    def test_severity_warning_for_label(self):
        """Test that environment label drift is warning."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        severity = detector._determine_drift_severity(
            "ConfigMap", "metadata.labels.environment"
        )
        assert severity == Severity.WARNING

    def test_severity_info_for_other(self):
        """Test that unknown field drift is info."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        severity = detector._determine_drift_severity(
            "ConfigMap", "data.SOME_OTHER_KEY"
        )
        assert severity == Severity.INFO


class TestDriftDetectorCriticalFields:
    """Tests for critical field identification."""

    def test_configmap_critical_fields(self):
        """Test critical fields for ConfigMap."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        fields = detector._get_critical_fields("ConfigMap")

        assert "data.ENVIRONMENT" in fields
        assert "data.NEPTUNE_ENDPOINT" in fields
        assert "data.OPENSEARCH_ENDPOINT" in fields
        assert "data.JOBS_TABLE_NAME" in fields
        assert "data.SNS_TOPIC_ARN" in fields

    def test_deployment_critical_fields(self):
        """Test critical fields for Deployment."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        fields = detector._get_critical_fields("Deployment")

        assert "spec.template.spec.containers.0.image" in fields
        assert "spec.template.spec.serviceAccountName" in fields

    def test_serviceaccount_critical_fields(self):
        """Test critical fields for ServiceAccount."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        fields = detector._get_critical_fields("ServiceAccount")

        # Uses bracket notation for keys containing dots
        assert "metadata.annotations[eks.amazonaws.com/role-arn]" in fields

    def test_common_fields_present(self):
        """Test that common fields are present for all resource types."""
        manager = MockBaselineManager("qa")
        detector = DriftDetector("qa", manager)

        for kind in ["ConfigMap", "Deployment", "ServiceAccount", "Secret"]:
            fields = detector._get_critical_fields(kind)
            assert "metadata.labels.environment" in fields
            assert "metadata.labels.app" in fields
