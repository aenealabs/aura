"""
Tests for K8s Namespace Service.

Tests EKS namespace management for test environments.
"""

import json
import platform

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from io import BytesIO
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from src.services.k8s_namespace_service import (
    K8sNamespaceService,
    K8sNamespaceServiceError,
    NamespaceCreationError,
    NamespaceDeletionError,
    NamespaceNotFoundError,
    NamespaceSpec,
    NamespaceStatus,
    create_quick_environment,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_lambda_client():
    """Create mock Lambda client."""
    client = MagicMock()
    return client


@pytest.fixture
def namespace_service(mock_lambda_client):
    """Create namespace service with mocked Lambda client."""
    with patch("boto3.client") as mock_client:
        mock_client.return_value = mock_lambda_client
        service = K8sNamespaceService(
            namespace_controller_function="test-namespace-controller",
            region="us-east-1",
        )
        service._lambda_client = mock_lambda_client
        return service


@pytest.fixture
def sample_spec():
    """Create sample namespace spec."""
    return NamespaceSpec(
        name="testenv-abc123",
        environment_id="env-abc123",
        user_id="user-123",
        cpu_quota="2",
        memory_quota="4Gi",
        pod_quota="10",
        ttl_hours=4,
    )


# ============================================================================
# NamespaceSpec Tests
# ============================================================================


class TestNamespaceSpec:
    """Test NamespaceSpec dataclass."""

    def test_default_values(self):
        """Test default values."""
        spec = NamespaceSpec(
            name="test-ns",
            environment_id="env-123",
            user_id="user-456",
        )
        assert spec.cpu_quota == "2"
        assert spec.memory_quota == "4Gi"
        assert spec.pod_quota == "10"
        assert spec.network_policy_enabled is True
        assert spec.ttl_hours == 4
        assert spec.labels == {}

    def test_custom_values(self):
        """Test custom values."""
        spec = NamespaceSpec(
            name="test-ns",
            environment_id="env-123",
            user_id="user-456",
            cpu_quota="4",
            memory_quota="8Gi",
            pod_quota="20",
            network_policy_enabled=False,
            ttl_hours=8,
            labels={"team": "platform"},
        )
        assert spec.cpu_quota == "4"
        assert spec.memory_quota == "8Gi"
        assert spec.network_policy_enabled is False
        assert spec.labels == {"team": "platform"}

    def test_to_dict(self):
        """Test to_dict conversion."""
        spec = NamespaceSpec(
            name="test-ns",
            environment_id="env-123",
            user_id="user-456",
        )
        result = spec.to_dict()

        assert result["name"] == "test-ns"
        assert result["environment_id"] == "env-123"
        assert result["user_id"] == "user-456"
        assert result["cpu_quota"] == "2"
        assert result["memory_quota"] == "4Gi"
        assert result["pod_quota"] == "10"
        assert result["network_policy_enabled"] is True
        assert result["ttl_hours"] == 4


# ============================================================================
# NamespaceStatus Tests
# ============================================================================


class TestNamespaceStatus:
    """Test NamespaceStatus dataclass."""

    def test_basic_status(self):
        """Test basic status creation."""
        status = NamespaceStatus(
            namespace="testenv-123",
            phase="Active",
        )
        assert status.namespace == "testenv-123"
        assert status.phase == "Active"
        assert status.environment_id is None
        assert status.error is None

    def test_full_status(self):
        """Test status with all fields."""
        status = NamespaceStatus(
            namespace="testenv-123",
            phase="Active",
            environment_id="env-123",
            user_id="user-456",
            ttl_hours=4,
            error=None,
        )
        assert status.environment_id == "env-123"
        assert status.user_id == "user-456"
        assert status.ttl_hours == 4

    def test_from_response_dict_body(self):
        """Test creating from response with dict body."""
        response = {
            "body": {
                "namespace": "testenv-abc",
                "phase": "Active",
                "environment_id": "env-abc",
                "user_id": "user-123",
                "ttl_hours": "4",
            }
        }
        status = NamespaceStatus.from_response(response)

        assert status.namespace == "testenv-abc"
        assert status.phase == "Active"
        assert status.environment_id == "env-abc"
        assert status.ttl_hours == 4

    def test_from_response_string_body(self):
        """Test creating from response with JSON string body."""
        response = {
            "body": json.dumps(
                {
                    "namespace": "testenv-xyz",
                    "phase": "Terminating",
                }
            )
        }
        status = NamespaceStatus.from_response(response)

        assert status.namespace == "testenv-xyz"
        assert status.phase == "Terminating"

    def test_from_response_empty_body(self):
        """Test creating from response with empty body."""
        response = {"body": {}}
        status = NamespaceStatus.from_response(response)

        assert status.namespace == ""
        assert status.phase == "Unknown"


# ============================================================================
# Exception Tests
# ============================================================================


class TestExceptions:
    """Test custom exceptions."""

    def test_base_exception(self):
        """Test K8sNamespaceServiceError."""
        with pytest.raises(K8sNamespaceServiceError):
            raise K8sNamespaceServiceError("Test error")

    def test_not_found_exception(self):
        """Test NamespaceNotFoundError."""
        with pytest.raises(NamespaceNotFoundError):
            raise NamespaceNotFoundError("Namespace not found")

    def test_creation_exception(self):
        """Test NamespaceCreationError."""
        with pytest.raises(NamespaceCreationError):
            raise NamespaceCreationError("Creation failed")

    def test_deletion_exception(self):
        """Test NamespaceDeletionError."""
        with pytest.raises(NamespaceDeletionError):
            raise NamespaceDeletionError("Deletion failed")

    def test_exception_inheritance(self):
        """Test exception inheritance."""
        assert issubclass(NamespaceNotFoundError, K8sNamespaceServiceError)
        assert issubclass(NamespaceCreationError, K8sNamespaceServiceError)
        assert issubclass(NamespaceDeletionError, K8sNamespaceServiceError)


# ============================================================================
# K8sNamespaceService Initialization Tests
# ============================================================================


class TestServiceInit:
    """Test K8sNamespaceService initialization."""

    def test_init(self):
        """Test basic initialization."""
        with patch("boto3.client") as mock_client:
            service = K8sNamespaceService(
                namespace_controller_function="test-function",
                region="us-west-2",
            )
            assert service.namespace_controller_function == "test-function"
            assert service.region == "us-west-2"
            mock_client.assert_called_with("lambda", region_name="us-west-2")


# ============================================================================
# Create Namespace Tests
# ============================================================================


class TestCreateNamespace:
    """Test namespace creation."""

    def test_create_success(self, namespace_service, mock_lambda_client, sample_spec):
        """Test successful namespace creation."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {
                        "statusCode": 200,
                        "body": {
                            "namespace": "testenv-abc123",
                            "phase": "Active",
                        },
                    }
                ).encode()
            )
        }

        status = namespace_service.create_namespace(sample_spec)

        assert status.namespace == "testenv-abc123"
        assert status.phase == "Active"
        assert status.environment_id == sample_spec.environment_id
        mock_lambda_client.invoke.assert_called_once()

    def test_create_failure(self, namespace_service, mock_lambda_client, sample_spec):
        """Test failed namespace creation."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {"statusCode": 500, "body": {"error": "Quota exceeded"}}
                ).encode()
            )
        }

        with pytest.raises(NamespaceCreationError, match="Quota exceeded"):
            namespace_service.create_namespace(sample_spec)

    def test_create_lambda_error(
        self, namespace_service, mock_lambda_client, sample_spec
    ):
        """Test Lambda function error during creation."""
        mock_lambda_client.invoke.return_value = {
            "FunctionError": "Unhandled",
            "Payload": BytesIO(
                json.dumps({"errorMessage": "Lambda function crashed"}).encode()
            ),
        }

        with pytest.raises(K8sNamespaceServiceError, match="Lambda function error"):
            namespace_service.create_namespace(sample_spec)

    def test_create_client_error(
        self, namespace_service, mock_lambda_client, sample_spec
    ):
        """Test boto3 ClientError during creation."""
        mock_lambda_client.invoke.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Function not found",
                }
            },
            "Invoke",
        )

        with pytest.raises(K8sNamespaceServiceError, match="Lambda invocation failed"):
            namespace_service.create_namespace(sample_spec)


# ============================================================================
# Delete Namespace Tests
# ============================================================================


class TestDeleteNamespace:
    """Test namespace deletion."""

    def test_delete_by_name_success(self, namespace_service, mock_lambda_client):
        """Test successful deletion by name."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {
                        "statusCode": 200,
                        "body": {"namespace": "testenv-abc", "status": "Terminating"},
                    }
                ).encode()
            )
        }

        result = namespace_service.delete_namespace(namespace_name="testenv-abc")

        assert result is True
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]["Payload"])
        assert payload["operation"] == "delete"
        assert payload["namespace_name"] == "testenv-abc"

    def test_delete_by_environment_id(self, namespace_service, mock_lambda_client):
        """Test deletion by environment ID."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {
                        "statusCode": 200,
                        "body": {
                            "namespace": "testenv-env123",
                            "status": "Terminating",
                        },
                    }
                ).encode()
            )
        }

        result = namespace_service.delete_namespace(environment_id="env-123")

        assert result is True
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]["Payload"])
        assert payload["environment_id"] == "env-123"

    def test_delete_no_identifier(self, namespace_service):
        """Test deletion without identifier raises error."""
        with pytest.raises(
            ValueError, match="Either namespace_name or environment_id required"
        ):
            namespace_service.delete_namespace()

    def test_delete_failure(self, namespace_service, mock_lambda_client):
        """Test failed deletion."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {"statusCode": 500, "body": {"error": "Namespace in use"}}
                ).encode()
            )
        }

        with pytest.raises(NamespaceDeletionError, match="Namespace in use"):
            namespace_service.delete_namespace(namespace_name="test-ns")


# ============================================================================
# Get Namespace Status Tests
# ============================================================================


class TestGetNamespaceStatus:
    """Test getting namespace status."""

    def test_get_status_success(self, namespace_service, mock_lambda_client):
        """Test successful status retrieval."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {
                        "statusCode": 200,
                        "body": {
                            "namespace": "testenv-abc",
                            "phase": "Active",
                            "environment_id": "env-abc",
                            "user_id": "user-123",
                            "ttl_hours": "4",
                        },
                    }
                ).encode()
            )
        }

        status = namespace_service.get_namespace_status(namespace_name="testenv-abc")

        assert status.namespace == "testenv-abc"
        assert status.phase == "Active"

    def test_get_status_by_environment_id(self, namespace_service, mock_lambda_client):
        """Test status retrieval by environment ID."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {
                        "statusCode": 200,
                        "body": {"namespace": "testenv-xyz", "phase": "Active"},
                    }
                ).encode()
            )
        }

        status = namespace_service.get_namespace_status(environment_id="env-xyz")

        assert status.namespace == "testenv-xyz"
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]["Payload"])
        assert payload["operation"] == "status"
        assert payload["environment_id"] == "env-xyz"

    def test_get_status_no_identifier(self, namespace_service):
        """Test status without identifier raises error."""
        with pytest.raises(
            ValueError, match="Either namespace_name or environment_id required"
        ):
            namespace_service.get_namespace_status()

    def test_get_status_not_found(self, namespace_service, mock_lambda_client):
        """Test status for non-existent namespace."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {"statusCode": 404, "body": {"error": "Namespace not found"}}
                ).encode()
            )
        }

        with pytest.raises(NamespaceNotFoundError):
            namespace_service.get_namespace_status(namespace_name="nonexistent")

    def test_get_status_error(self, namespace_service, mock_lambda_client):
        """Test status retrieval error."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {"statusCode": 500, "body": {"error": "Internal error"}}
                ).encode()
            )
        }

        with pytest.raises(K8sNamespaceServiceError, match="Internal error"):
            namespace_service.get_namespace_status(namespace_name="test-ns")


# ============================================================================
# Namespace Exists Tests
# ============================================================================


class TestNamespaceExists:
    """Test namespace existence check."""

    def test_exists_true(self, namespace_service, mock_lambda_client):
        """Test namespace exists returns True."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {
                        "statusCode": 200,
                        "body": {"namespace": "testenv-abc", "phase": "Active"},
                    }
                ).encode()
            )
        }

        result = namespace_service.namespace_exists(namespace_name="testenv-abc")

        assert result is True

    def test_exists_false_not_found(self, namespace_service, mock_lambda_client):
        """Test namespace not found returns False."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {"statusCode": 404, "body": {"error": "Namespace not found"}}
                ).encode()
            )
        }

        result = namespace_service.namespace_exists(namespace_name="nonexistent")

        assert result is False

    def test_exists_false_on_error(self, namespace_service, mock_lambda_client):
        """Test service error returns False."""
        mock_lambda_client.invoke.return_value = {
            "FunctionError": "Unhandled",
            "Payload": BytesIO(
                json.dumps({"errorMessage": "Function crashed"}).encode()
            ),
        }

        result = namespace_service.namespace_exists(namespace_name="test-ns")

        assert result is False


# ============================================================================
# Quick Environment Helper Tests
# ============================================================================


class TestCreateQuickEnvironment:
    """Test create_quick_environment helper function."""

    def test_create_quick_environment_success(self):
        """Test quick environment creation."""
        with patch(
            "src.services.k8s_namespace_service.K8sNamespaceService"
        ) as MockService:
            mock_service = MagicMock()
            mock_service.create_namespace.return_value = NamespaceStatus(
                namespace="testenv-env123",
                phase="Active",
                environment_id="env-123",
                user_id="user-456",
            )
            MockService.return_value = mock_service

            result = create_quick_environment(
                environment_id="env-123",
                user_id="user-456",
                namespace_controller_function="test-function",
                region="us-east-1",
                cpu_quota="2",
                memory_quota="4Gi",
                ttl_hours=4,
            )

            assert result.namespace == "testenv-env123"
            assert result.phase == "Active"
            mock_service.create_namespace.assert_called_once()

    def test_create_quick_environment_custom_resources(self):
        """Test quick environment with custom resources."""
        with patch(
            "src.services.k8s_namespace_service.K8sNamespaceService"
        ) as MockService:
            mock_service = MagicMock()
            mock_service.create_namespace.return_value = NamespaceStatus(
                namespace="testenv-custom",
                phase="Active",
            )
            MockService.return_value = mock_service

            create_quick_environment(
                environment_id="custom-env",
                user_id="user-789",
                namespace_controller_function="test-function",
                cpu_quota="4",
                memory_quota="8Gi",
                ttl_hours=8,
            )

            # Verify spec was created with custom values
            call_args = mock_service.create_namespace.call_args
            spec = call_args[0][0]
            assert spec.cpu_quota == "4"
            assert spec.memory_quota == "8Gi"
            assert spec.ttl_hours == 8


# ============================================================================
# Response Parsing Tests
# ============================================================================


class TestResponseParsing:
    """Test response parsing edge cases."""

    def test_create_with_string_body(
        self, namespace_service, mock_lambda_client, sample_spec
    ):
        """Test creation with JSON string body."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {
                        "statusCode": 200,
                        "body": json.dumps(
                            {"namespace": "testenv-str", "phase": "Active"}
                        ),
                    }
                ).encode()
            )
        }

        status = namespace_service.create_namespace(sample_spec)
        # Body is parsed and namespace is extracted from response
        assert status.namespace == "testenv-str"

    def test_delete_with_string_body(self, namespace_service, mock_lambda_client):
        """Test deletion with JSON string body."""
        mock_lambda_client.invoke.return_value = {
            "Payload": BytesIO(
                json.dumps(
                    {
                        "statusCode": 200,
                        "body": json.dumps(
                            {"namespace": "testenv-del", "status": "Terminating"}
                        ),
                    }
                ).encode()
            )
        }

        result = namespace_service.delete_namespace(namespace_name="testenv-del")
        assert result is True
