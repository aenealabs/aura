"""
Service for managing EKS namespaces for test environments.

This service provides a high-level interface for:
- Creating test environment namespaces with resource quotas
- Deleting namespaces
- Getting namespace status

Uses the namespace controller Lambda for actual kubectl operations.

Part of ADR-039 Phase 4: Advanced Features
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class NamespaceSpec:
    """Specification for a test environment namespace."""

    name: str
    environment_id: str
    user_id: str
    cpu_quota: str = "2"
    memory_quota: str = "4Gi"
    pod_quota: str = "10"
    network_policy_enabled: bool = True
    ttl_hours: int = 4
    labels: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for Lambda invocation."""
        return {
            "name": self.name,
            "environment_id": self.environment_id,
            "user_id": self.user_id,
            "cpu_quota": self.cpu_quota,
            "memory_quota": self.memory_quota,
            "pod_quota": self.pod_quota,
            "network_policy_enabled": self.network_policy_enabled,
            "ttl_hours": self.ttl_hours,
            "labels": self.labels,
        }


@dataclass
class NamespaceStatus:
    """Status information for a namespace."""

    namespace: str
    phase: str
    environment_id: str | None = None
    user_id: str | None = None
    ttl_hours: int | None = None
    error: str | None = None

    @classmethod
    def from_response(cls, response: dict) -> "NamespaceStatus":
        """Create from Lambda response."""
        body = response.get("body", {})
        if isinstance(body, str):
            body = json.loads(body)

        return cls(
            namespace=body.get("namespace", ""),
            phase=body.get("phase", "Unknown"),
            environment_id=body.get("environment_id"),
            user_id=body.get("user_id"),
            ttl_hours=int(body["ttl_hours"]) if body.get("ttl_hours") else None,
            error=body.get("error"),
        )


class K8sNamespaceServiceError(Exception):
    """Base exception for namespace service errors."""


class NamespaceNotFoundError(K8sNamespaceServiceError):
    """Raised when a namespace is not found."""


class NamespaceCreationError(K8sNamespaceServiceError):
    """Raised when namespace creation fails."""


class NamespaceDeletionError(K8sNamespaceServiceError):
    """Raised when namespace deletion fails."""


class K8sNamespaceService:
    """
    Service for managing EKS namespaces via Lambda.

    This service invokes the namespace controller Lambda to perform
    kubectl operations for creating and managing test environment namespaces.
    """

    def __init__(
        self, namespace_controller_function: str, region: str = "us-east-1"
    ) -> None:
        """
        Initialize the namespace service.

        Args:
            namespace_controller_function: Name or ARN of the namespace controller Lambda
            region: AWS region
        """
        self.namespace_controller_function = namespace_controller_function
        self.region = region
        self._lambda_client = boto3.client("lambda", region_name=region)
        logger.info(
            f"K8sNamespaceService initialized with function: {namespace_controller_function}"
        )

    def _invoke_controller(self, payload: dict) -> dict:
        """
        Invoke the namespace controller Lambda.

        Args:
            payload: Request payload

        Returns:
            Response from Lambda

        Raises:
            K8sNamespaceServiceError: If invocation fails
        """
        try:
            response = self._lambda_client.invoke(
                FunctionName=self.namespace_controller_function,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )

            # Check for function errors
            if "FunctionError" in response:
                error_payload = json.loads(response["Payload"].read())
                raise K8sNamespaceServiceError(
                    f"Lambda function error: {error_payload.get('errorMessage', 'Unknown error')}"
                )

            # Parse response
            result = json.loads(response["Payload"].read())  # type: ignore[unreachable]
            return result

        except ClientError as e:
            logger.error(f"Failed to invoke namespace controller: {e}")
            raise K8sNamespaceServiceError(f"Lambda invocation failed: {e}")

    def create_namespace(self, spec: NamespaceSpec) -> NamespaceStatus:
        """
        Create a new test environment namespace.

        Args:
            spec: Namespace specification

        Returns:
            NamespaceStatus with creation result

        Raises:
            NamespaceCreationError: If creation fails
        """
        logger.info(f"Creating namespace for environment: {spec.environment_id}")

        payload = {"operation": "create", **spec.to_dict()}

        response = self._invoke_controller(payload)

        status_code = response.get("statusCode", 500)
        body = response.get("body", {})
        if isinstance(body, str):
            body = json.loads(body)

        if status_code != 200:
            error_msg = body.get("error", "Unknown error")
            logger.error(f"Namespace creation failed: {error_msg}")
            raise NamespaceCreationError(error_msg)

        logger.info(f"Namespace created: {body.get('namespace')}")
        return NamespaceStatus(
            namespace=body.get("namespace", spec.name),
            phase="Active",
            environment_id=spec.environment_id,
            user_id=spec.user_id,
            ttl_hours=spec.ttl_hours,
        )

    def delete_namespace(
        self, namespace_name: str | None = None, environment_id: str | None = None
    ) -> bool:
        """
        Delete a test environment namespace.

        Args:
            namespace_name: Name of the namespace to delete
            environment_id: Or environment ID (namespace will be derived)

        Returns:
            True if deletion initiated successfully

        Raises:
            NamespaceDeletionError: If deletion fails
        """
        if not namespace_name and not environment_id:
            raise ValueError("Either namespace_name or environment_id required")

        logger.info(f"Deleting namespace: {namespace_name or environment_id}")

        payload = {
            "operation": "delete",
            "namespace_name": namespace_name,
            "environment_id": environment_id,
        }

        response = self._invoke_controller(payload)

        status_code = response.get("statusCode", 500)
        body = response.get("body", {})
        if isinstance(body, str):
            body = json.loads(body)

        if status_code != 200:
            error_msg = body.get("error", "Unknown error")
            logger.error(f"Namespace deletion failed: {error_msg}")
            raise NamespaceDeletionError(error_msg)

        logger.info(f"Namespace deletion initiated: {body.get('namespace')}")
        return True

    def get_namespace_status(
        self, namespace_name: str | None = None, environment_id: str | None = None
    ) -> NamespaceStatus:
        """
        Get the status of a test environment namespace.

        Args:
            namespace_name: Name of the namespace
            environment_id: Or environment ID (namespace will be derived)

        Returns:
            NamespaceStatus with current status

        Raises:
            NamespaceNotFoundError: If namespace doesn't exist
        """
        if not namespace_name and not environment_id:
            raise ValueError("Either namespace_name or environment_id required")

        logger.info(f"Getting namespace status: {namespace_name or environment_id}")

        payload = {
            "operation": "status",
            "namespace_name": namespace_name,
            "environment_id": environment_id,
        }

        response = self._invoke_controller(payload)

        status_code = response.get("statusCode", 500)
        body = response.get("body", {})
        if isinstance(body, str):
            body = json.loads(body)

        if status_code == 404:
            raise NamespaceNotFoundError(body.get("error", "Namespace not found"))

        if status_code != 200:
            raise K8sNamespaceServiceError(body.get("error", "Unknown error"))

        return NamespaceStatus.from_response(response)

    def namespace_exists(
        self, namespace_name: str | None = None, environment_id: str | None = None
    ) -> bool:
        """
        Check if a namespace exists.

        Args:
            namespace_name: Name of the namespace
            environment_id: Or environment ID

        Returns:
            True if namespace exists
        """
        try:
            self.get_namespace_status(namespace_name, environment_id)
            return True
        except NamespaceNotFoundError:
            return False
        except K8sNamespaceServiceError:
            return False


def create_quick_environment(
    environment_id: str,
    user_id: str,
    namespace_controller_function: str,
    region: str = "us-east-1",
    cpu_quota: str = "2",
    memory_quota: str = "4Gi",
    ttl_hours: int = 4,
) -> NamespaceStatus:
    """
    Convenience function to create a quick test environment (EKS namespace).

    This is a simplified interface for creating test environments without
    the full Service Catalog provisioning workflow.

    Args:
        environment_id: Unique environment identifier
        user_id: User creating the environment
        namespace_controller_function: Lambda function name
        region: AWS region
        cpu_quota: CPU resource quota
        memory_quota: Memory resource quota
        ttl_hours: Time-to-live in hours

    Returns:
        NamespaceStatus with creation result
    """
    service = K8sNamespaceService(
        namespace_controller_function=namespace_controller_function, region=region
    )

    spec = NamespaceSpec(
        name=f"testenv-{environment_id[:12]}",
        environment_id=environment_id,
        user_id=user_id,
        cpu_quota=cpu_quota,
        memory_quota=memory_quota,
        ttl_hours=ttl_hours,
        labels={"type": "quick", "created_at": datetime.now(timezone.utc).isoformat()},
    )

    return service.create_namespace(spec)
