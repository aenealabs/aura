"""
Unit tests for namespace_controller.py Lambda handler.

Tests cover:
- Namespace manifest generation
- kubectl subprocess calls (mocked)
- Create, delete, status operations
- Error handling
- kubeconfig generation

Part of ADR-039 Phase 4: Advanced Features
"""

import importlib
import json
import os
import platform
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# Set environment variables before importing Lambda
os.environ.setdefault("EKS_CLUSTER_NAME", "test-cluster")
os.environ.setdefault("STATE_TABLE", "test-state-table")
os.environ.setdefault("SNS_TOPIC", "")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PROJECT_NAME", "aura")
os.environ.setdefault("METRICS_NAMESPACE", "aura/TestEnvironments")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

# Import using importlib (lambda is a reserved keyword)
namespace_controller = importlib.import_module("src.lambda.namespace_controller")


class TestNamespaceSpec:
    """Tests for NamespaceSpec dataclass."""

    def test_creates_spec_with_defaults(self):
        """Test spec creation with default values."""
        spec = namespace_controller.NamespaceSpec(
            name="testenv-abc123", environment_id="env-abc123", user_id="user-456"
        )

        assert spec.name == "testenv-abc123"
        assert spec.cpu_quota == "2"
        assert spec.memory_quota == "4Gi"
        assert spec.pod_quota == "10"
        assert spec.network_policy_enabled is True
        assert spec.ttl_hours == 4

    def test_creates_spec_with_custom_values(self):
        """Test spec creation with custom values."""
        spec = namespace_controller.NamespaceSpec(
            name="testenv-abc123",
            environment_id="env-abc123",
            user_id="user-456",
            cpu_quota="4",
            memory_quota="8Gi",
            pod_quota="20",
            network_policy_enabled=False,
            ttl_hours=8,
        )

        assert spec.cpu_quota == "4"
        assert spec.memory_quota == "8Gi"
        assert spec.network_policy_enabled is False
        assert spec.ttl_hours == 8


class TestGenerateNamespaceManifest:
    """Tests for generate_namespace_manifest function."""

    def test_generates_namespace_yaml(self):
        """Test namespace manifest generation."""
        spec = namespace_controller.NamespaceSpec(
            name="testenv-abc123", environment_id="env-abc123", user_id="user-456"
        )

        manifest = namespace_controller.generate_namespace_manifest(spec)

        # Check that manifest contains expected resources
        assert "kind: Namespace" in manifest
        assert "name: testenv-abc123" in manifest
        assert "kind: ResourceQuota" in manifest
        assert "kind: LimitRange" in manifest
        assert "kind: ServiceAccount" in manifest

    def test_includes_network_policy_when_enabled(self):
        """Test network policy inclusion."""
        spec = namespace_controller.NamespaceSpec(
            name="testenv-abc123",
            environment_id="env-abc123",
            user_id="user-456",
            network_policy_enabled=True,
        )

        manifest = namespace_controller.generate_namespace_manifest(spec)

        assert "kind: NetworkPolicy" in manifest
        assert "default-deny" in manifest

    def test_excludes_network_policy_when_disabled(self):
        """Test network policy exclusion."""
        spec = namespace_controller.NamespaceSpec(
            name="testenv-abc123",
            environment_id="env-abc123",
            user_id="user-456",
            network_policy_enabled=False,
        )

        manifest = namespace_controller.generate_namespace_manifest(spec)

        assert "kind: NetworkPolicy" not in manifest

    def test_includes_labels(self):
        """Test that labels are included in manifest."""
        spec = namespace_controller.NamespaceSpec(
            name="testenv-abc123",
            environment_id="env-abc123",
            user_id="user-456",
            labels={"custom-label": "custom-value"},
        )

        manifest = namespace_controller.generate_namespace_manifest(spec)

        assert "aura.ai/environment-id" in manifest
        assert "aura.ai/user-id" in manifest
        assert "custom-label" in manifest


class TestKubectlOperations:
    """Tests for kubectl subprocess operations."""

    @patch("subprocess.run")
    def test_kubectl_apply_success(self, mock_run):
        """Test successful kubectl apply."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="namespace/testenv-abc123 created", stderr=""
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("test")
            kubeconfig_path = f.name

        try:
            success, output = namespace_controller.kubectl_apply(
                kubeconfig_path, "apiVersion: v1\nkind: Namespace"
            )

            assert success is True
            assert "created" in output
            mock_run.assert_called_once()
        finally:
            os.unlink(kubeconfig_path)

    @patch("subprocess.run")
    def test_kubectl_apply_failure(self, mock_run):
        """Test kubectl apply failure handling."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error: resource already exists"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("test")
            kubeconfig_path = f.name

        try:
            success, output = namespace_controller.kubectl_apply(
                kubeconfig_path, "apiVersion: v1\nkind: Namespace"
            )

            assert success is False
            assert "error" in output.lower()
        finally:
            os.unlink(kubeconfig_path)

    @patch("subprocess.run")
    def test_kubectl_delete_namespace_success(self, mock_run):
        """Test successful namespace deletion."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout='namespace "testenv-abc123" deleted', stderr=""
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("test")
            kubeconfig_path = f.name

        try:
            success, output = namespace_controller.kubectl_delete_namespace(
                kubeconfig_path, "testenv-abc123"
            )

            assert success is True
        finally:
            os.unlink(kubeconfig_path)


class TestHandler:
    """Tests for the Lambda handler function."""

    @patch.object(namespace_controller, "get_kubeconfig")
    @patch.object(namespace_controller, "kubectl_apply")
    @patch.object(namespace_controller, "update_environment_state")
    @patch.object(namespace_controller, "publish_metric")
    def test_create_namespace_success(
        self, mock_metric, mock_update, mock_apply, mock_kubeconfig
    ):
        """Test successful namespace creation."""
        mock_kubeconfig.return_value = "/tmp/kubeconfig.yaml"
        mock_apply.return_value = (True, "namespace created")
        mock_update.return_value = True

        event = {
            "operation": "create",
            "environment_id": "env-abc123",
            "user_id": "user-456",
        }
        context = MagicMock()

        response = namespace_controller.handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "namespace" in body
        mock_update.assert_called_once()

    @patch.object(namespace_controller, "get_kubeconfig")
    @patch.object(namespace_controller, "kubectl_delete_namespace")
    @patch.object(namespace_controller, "update_environment_state")
    @patch.object(namespace_controller, "publish_metric")
    def test_delete_namespace_success(
        self, mock_metric, mock_update, mock_delete, mock_kubeconfig
    ):
        """Test successful namespace deletion."""
        mock_kubeconfig.return_value = "/tmp/kubeconfig.yaml"
        mock_delete.return_value = (True, "namespace deleted")

        event = {"operation": "delete", "environment_id": "env-abc123"}
        context = MagicMock()

        response = namespace_controller.handler(event, context)

        assert response["statusCode"] == 200

    @patch.object(namespace_controller, "get_kubeconfig")
    @patch.object(namespace_controller, "kubectl_get_namespace")
    def test_get_namespace_status(self, mock_get, mock_kubeconfig):
        """Test namespace status retrieval."""
        mock_kubeconfig.return_value = "/tmp/kubeconfig.yaml"
        mock_get.return_value = {
            "metadata": {
                "name": "testenv-abc123",
                "labels": {
                    "aura.ai/environment-id": "env-abc123",
                    "aura.ai/user-id": "user-456",
                },
            },
            "status": {"phase": "Active"},
        }

        event = {"operation": "status", "environment_id": "env-abc123"}
        context = MagicMock()

        response = namespace_controller.handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["phase"] == "Active"

    def test_handler_requires_cluster_name(self, monkeypatch):
        """Test handler fails without EKS cluster name."""
        # Save original value
        original = os.environ.get("EKS_CLUSTER_NAME")
        try:
            os.environ["EKS_CLUSTER_NAME"] = ""

            # Need to reimport to pick up new env var
            import importlib

            nc = importlib.import_module("src.lambda.namespace_controller")
            importlib.reload(nc)

            event = {
                "operation": "create",
                "environment_id": "env-123",
                "user_id": "user-456",
            }
            context = MagicMock()

            response = nc.handler(event, context)

            assert response["statusCode"] == 500
            assert "not configured" in json.loads(response["body"])["error"]
        finally:
            # Restore original value
            if original:
                os.environ["EKS_CLUSTER_NAME"] = original
            else:
                os.environ["EKS_CLUSTER_NAME"] = "test-cluster"
            # Reload again to restore original state
            importlib.reload(namespace_controller)

    def test_handler_rejects_unknown_operation(self):
        """Test handler rejects unknown operations."""
        event = {"operation": "unknown"}
        context = MagicMock()

        response = namespace_controller.handler(event, context)

        assert response["statusCode"] == 400
        assert "Unknown operation" in json.loads(response["body"])["error"]
