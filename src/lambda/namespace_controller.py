"""
Lambda handler for EKS namespace lifecycle management.

Uses kubectl via Lambda layer (subprocess calls to kubectl binary).
This approach matches the dns-blocklist pattern and is simpler for IAM.

Part of ADR-039 Phase 4: Advanced Features (Layer 7.9)
"""

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

# Import lazy-initialized AWS clients (Issue #466)
try:
    from aws_clients import (
        get_cloudwatch_client,
        get_dynamodb_resource,
        get_eks_client,
        get_sns_client,
        get_sts_client,
    )
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_cloudwatch_client = _aws_clients.get_cloudwatch_client
    get_dynamodb_resource = _aws_clients.get_dynamodb_resource
    get_eks_client = _aws_clients.get_eks_client
    get_sns_client = _aws_clients.get_sns_client
    get_sts_client = _aws_clients.get_sts_client

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
EKS_CLUSTER_NAME = os.environ.get("EKS_CLUSTER_NAME", "")
STATE_TABLE = os.environ.get("STATE_TABLE", "")
SNS_TOPIC = os.environ.get("SNS_TOPIC", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "aura")
METRICS_NAMESPACE = os.environ.get("METRICS_NAMESPACE", "aura/TestEnvironments")

# Default resource quotas
DEFAULT_CPU_QUOTA = os.environ.get("DEFAULT_CPU_QUOTA", "2")
DEFAULT_MEMORY_QUOTA = os.environ.get("DEFAULT_MEMORY_QUOTA", "4Gi")
DEFAULT_POD_QUOTA = os.environ.get("DEFAULT_POD_QUOTA", "10")
DEFAULT_TTL_HOURS = int(os.environ.get("DEFAULT_TTL_HOURS", "4"))

# Path to kubectl binary (from Lambda layer)
KUBECTL_PATH = "/opt/bin/kubectl"


class NamespaceSpec:
    """Specification for a test environment namespace."""

    def __init__(
        self,
        name: str,
        environment_id: str,
        user_id: str,
        cpu_quota: str = DEFAULT_CPU_QUOTA,
        memory_quota: str = DEFAULT_MEMORY_QUOTA,
        pod_quota: str = DEFAULT_POD_QUOTA,
        network_policy_enabled: bool = True,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        labels: dict | None = None,
    ):
        self.name = name
        self.environment_id = environment_id
        self.user_id = user_id
        self.cpu_quota = cpu_quota
        self.memory_quota = memory_quota
        self.pod_quota = pod_quota
        self.network_policy_enabled = network_policy_enabled
        self.ttl_hours = ttl_hours
        self.labels = labels or {}


def get_kubeconfig(cluster_name: str) -> str:
    """
    Generate kubeconfig for EKS cluster using AWS credentials.

    Args:
        cluster_name: Name of the EKS cluster

    Returns:
        Path to temporary kubeconfig file
    """
    try:
        # Get cluster info
        cluster_info = get_eks_client().describe_cluster(name=cluster_name)["cluster"]
        endpoint = cluster_info["endpoint"]
        ca_data = cluster_info["certificateAuthority"]["data"]

        # Get current identity for token
        _identity = get_sts_client().get_caller_identity()  # noqa: F841
        region = os.environ.get("AWS_REGION", "us-east-1")

        # Generate kubeconfig
        kubeconfig = f"""
apiVersion: v1
kind: Config
clusters:
- cluster:
    server: {endpoint}
    certificate-authority-data: {ca_data}
  name: {cluster_name}
contexts:
- context:
    cluster: {cluster_name}
    user: aws
  name: {cluster_name}
current-context: {cluster_name}
users:
- name: aws
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: aws
      args:
        - eks
        - get-token
        - --cluster-name
        - {cluster_name}
        - --region
        - {region}
"""

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(kubeconfig)
            return f.name

    except ClientError as e:
        logger.error(f"Failed to generate kubeconfig: {e}")
        raise


def generate_namespace_manifest(spec: NamespaceSpec) -> str:
    """
    Generate Kubernetes manifests for namespace with resource quota and network policy.

    Args:
        spec: Namespace specification

    Returns:
        YAML manifest string
    """
    labels = {
        "app.kubernetes.io/managed-by": "aura-test-envs",
        "aura.ai/environment-id": spec.environment_id,
        "aura.ai/user-id": spec.user_id,
        "aura.ai/ttl-hours": str(spec.ttl_hours),
        **spec.labels,
    }
    labels_yaml = "\n    ".join([f'{k}: "{v}"' for k, v in labels.items()])

    manifest = f"""---
apiVersion: v1
kind: Namespace
metadata:
  name: {spec.name}
  labels:
    {labels_yaml}
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: {spec.name}-quota
  namespace: {spec.name}
spec:
  hard:
    requests.cpu: "{spec.cpu_quota}"
    requests.memory: "{spec.memory_quota}"
    limits.cpu: "{spec.cpu_quota}"
    limits.memory: "{spec.memory_quota}"
    pods: "{spec.pod_quota}"
    services: "5"
    secrets: "10"
    configmaps: "10"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: {spec.name}-limits
  namespace: {spec.name}
spec:
  limits:
  - default:
      cpu: "500m"
      memory: "512Mi"
    defaultRequest:
      cpu: "100m"
      memory: "128Mi"
    type: Container
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: default
  namespace: {spec.name}
  labels:
    aura.ai/environment-id: "{spec.environment_id}"
"""

    # Add network policy if enabled
    if spec.network_policy_enabled:
        manifest += f"""---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {spec.name}-default-deny
  namespace: {spec.name}
spec:
  podSelector: {{}}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: {spec.name}
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: {spec.name}
"""

    return manifest


def kubectl_apply(kubeconfig_path: str, manifest: str) -> tuple[bool, str]:
    """
    Apply Kubernetes manifest using kubectl.

    Args:
        kubeconfig_path: Path to kubeconfig file
        manifest: YAML manifest to apply

    Returns:
        Tuple of (success, output/error)
    """
    # Write manifest to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(manifest)
        manifest_path = f.name

    try:
        result = subprocess.run(
            [
                KUBECTL_PATH,
                "--kubeconfig",
                kubeconfig_path,
                "apply",
                "-f",
                manifest_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            logger.info(f"kubectl apply successful: {result.stdout}")
            return True, result.stdout
        else:
            logger.error(f"kubectl apply failed: {result.stderr}")
            return False, result.stderr

    except subprocess.TimeoutExpired:
        return False, "kubectl command timed out"
    except FileNotFoundError:
        return False, f"kubectl not found at {KUBECTL_PATH}"
    finally:
        # Clean up manifest file
        try:
            os.unlink(manifest_path)
        except OSError:
            pass


def kubectl_delete_namespace(kubeconfig_path: str, namespace: str) -> tuple[bool, str]:
    """
    Delete Kubernetes namespace using kubectl.

    Args:
        kubeconfig_path: Path to kubeconfig file
        namespace: Namespace name to delete

    Returns:
        Tuple of (success, output/error)
    """
    try:
        result = subprocess.run(
            [
                KUBECTL_PATH,
                "--kubeconfig",
                kubeconfig_path,
                "delete",
                "namespace",
                namespace,
                "--ignore-not-found",
                "--wait=false",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            logger.info(f"Namespace deletion initiated: {result.stdout}")
            return True, result.stdout
        else:
            logger.error(f"Namespace deletion failed: {result.stderr}")
            return False, result.stderr

    except subprocess.TimeoutExpired:
        return False, "kubectl command timed out"
    except FileNotFoundError:
        return False, f"kubectl not found at {KUBECTL_PATH}"


def kubectl_get_namespace(kubeconfig_path: str, namespace: str) -> dict | None:
    """
    Get namespace status using kubectl.

    Args:
        kubeconfig_path: Path to kubeconfig file
        namespace: Namespace name

    Returns:
        Namespace info dict or None if not found
    """
    try:
        result = subprocess.run(
            [
                KUBECTL_PATH,
                "--kubeconfig",
                kubeconfig_path,
                "get",
                "namespace",
                namespace,
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            loaded: dict[str, Any] = json.loads(result.stdout)
            return loaded
        else:
            return None

    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def update_environment_state(
    environment_id: str,
    status: str,
    namespace_name: str | None = None,
    error_message: str | None = None,
) -> bool:
    """Update environment state in DynamoDB."""
    if not STATE_TABLE:
        return False

    table = get_dynamodb_resource().Table(STATE_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    update_expr = "SET #status = :status, updated_at = :now"
    expr_values: dict[str, Any] = {":status": status, ":now": now}

    if namespace_name:
        update_expr += ", namespace_name = :ns"
        expr_values[":ns"] = namespace_name

    if error_message:
        update_expr += ", error_message = :error"
        expr_values[":error"] = error_message

    try:
        table.update_item(
            Key={"environment_id": environment_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues=expr_values,
        )
        return True
    except ClientError as e:
        logger.error(f"Failed to update environment state: {e}")
        return False


def publish_metric(metric_name: str, value: float = 1.0, unit: str = "Count") -> None:
    """Publish a CloudWatch metric."""
    try:
        get_cloudwatch_client().put_metric_data(
            Namespace=METRICS_NAMESPACE,
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Value": value,
                    "Unit": unit,
                    "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
                }
            ],
        )
    except ClientError as e:
        logger.warning(f"Failed to publish metric {metric_name}: {e}")


def create_namespace(event: dict) -> dict:
    """
    Create a new test environment namespace.

    Args:
        event: Request with namespace specification

    Returns:
        Response with creation result
    """
    environment_id = event.get("environment_id", "")
    user_id = event.get("user_id", "")

    if not environment_id or not user_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "environment_id and user_id required"}),
        }

    # Generate namespace name
    namespace_name = f"testenv-{environment_id[:12]}"

    spec = NamespaceSpec(
        name=namespace_name,
        environment_id=environment_id,
        user_id=user_id,
        cpu_quota=event.get("cpu_quota", DEFAULT_CPU_QUOTA),
        memory_quota=event.get("memory_quota", DEFAULT_MEMORY_QUOTA),
        pod_quota=event.get("pod_quota", DEFAULT_POD_QUOTA),
        network_policy_enabled=event.get("network_policy_enabled", True),
        ttl_hours=event.get("ttl_hours", DEFAULT_TTL_HOURS),
        labels=event.get("labels", {}),
    )

    # Generate kubeconfig
    try:
        kubeconfig_path = get_kubeconfig(EKS_CLUSTER_NAME)
    except Exception as e:
        update_environment_state(environment_id, "failed", error_message=str(e))
        publish_metric("NamespaceCreationFailed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Failed to get kubeconfig: {e}"}),
        }

    try:
        # Generate and apply manifest
        manifest = generate_namespace_manifest(spec)
        success, output = kubectl_apply(kubeconfig_path, manifest)

        if success:
            update_environment_state(
                environment_id, "active", namespace_name=namespace_name
            )
            publish_metric("NamespacesCreated")
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Namespace created successfully",
                        "namespace": namespace_name,
                        "environment_id": environment_id,
                    }
                ),
            }
        else:
            update_environment_state(environment_id, "failed", error_message=output)
            publish_metric("NamespaceCreationFailed")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"kubectl apply failed: {output}"}),
            }
    finally:
        # Clean up kubeconfig
        try:
            os.unlink(kubeconfig_path)
        except OSError:
            pass


def delete_namespace(event: dict) -> dict:
    """
    Delete a test environment namespace.

    Args:
        event: Request with namespace name or environment_id

    Returns:
        Response with deletion result
    """
    namespace_name = event.get("namespace_name", "")
    environment_id = event.get("environment_id", "")

    if not namespace_name and environment_id:
        namespace_name = f"testenv-{environment_id[:12]}"

    if not namespace_name:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "namespace_name or environment_id required"}),
        }

    # Generate kubeconfig
    try:
        kubeconfig_path = get_kubeconfig(EKS_CLUSTER_NAME)
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Failed to get kubeconfig: {e}"}),
        }

    try:
        success, output = kubectl_delete_namespace(kubeconfig_path, namespace_name)

        if success:
            if environment_id:
                update_environment_state(environment_id, "terminated")
            publish_metric("NamespacesDeleted")
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Namespace deletion initiated",
                        "namespace": namespace_name,
                    }
                ),
            }
        else:
            publish_metric("NamespaceDeletionFailed")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"kubectl delete failed: {output}"}),
            }
    finally:
        try:
            os.unlink(kubeconfig_path)
        except OSError:
            pass


def get_namespace_status(event: dict) -> dict:
    """
    Get the status of a test environment namespace.

    Args:
        event: Request with namespace name or environment_id

    Returns:
        Response with namespace status
    """
    namespace_name = event.get("namespace_name", "")
    environment_id = event.get("environment_id", "")

    if not namespace_name and environment_id:
        namespace_name = f"testenv-{environment_id[:12]}"

    if not namespace_name:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "namespace_name or environment_id required"}),
        }

    try:
        kubeconfig_path = get_kubeconfig(EKS_CLUSTER_NAME)
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Failed to get kubeconfig: {e}"}),
        }

    try:
        ns_info = kubectl_get_namespace(kubeconfig_path, namespace_name)

        if ns_info:
            phase = ns_info.get("status", {}).get("phase", "Unknown")
            labels = ns_info.get("metadata", {}).get("labels", {})
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "namespace": namespace_name,
                        "phase": phase,
                        "environment_id": labels.get("aura.ai/environment-id", ""),
                        "user_id": labels.get("aura.ai/user-id", ""),
                        "ttl_hours": labels.get("aura.ai/ttl-hours", ""),
                    }
                ),
            }
        else:
            return {
                "statusCode": 404,
                "body": json.dumps(
                    {"error": "Namespace not found", "namespace": namespace_name}
                ),
            }
    finally:
        try:
            os.unlink(kubeconfig_path)
        except OSError:
            pass


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for EKS namespace controller.

    Supported operations:
    - create: Create a new namespace with resource quotas
    - delete: Delete a namespace
    - status: Get namespace status

    Args:
        event: Request event with operation and parameters
        context: Lambda context

    Returns:
        Response with operation result
    """
    logger.info(f"Namespace controller invoked: {json.dumps(event)}")

    if not EKS_CLUSTER_NAME:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "EKS_CLUSTER_NAME not configured"}),
        }

    operation = event.get("operation", "status")

    if operation == "create":
        return create_namespace(event)
    elif operation == "delete":
        return delete_namespace(event)
    elif operation == "status":
        return get_namespace_status(event)
    else:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Unknown operation: {operation}"}),
        }
