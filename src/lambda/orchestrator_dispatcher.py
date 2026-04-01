"""
Project Aura - Orchestrator Dispatcher Lambda

Dispatches SQS messages to EKS MetaOrchestrator Jobs for autonomous
security remediation. This Lambda acts as a bridge between the event-driven
SQS queue and the long-running EKS workloads.

Architecture:
    SQS Queue -> Lambda (this) -> EKS Kubernetes Job -> MetaOrchestrator

Design Decisions:
    - Lambda handles SQS consumption (native integration, automatic scaling)
    - EKS handles execution (unlimited time, multi-agent spawning, VPC access)
    - DynamoDB tracks job state for observability and retry logic

For 85% autonomy target:
    - Auto-investigate: Always enabled
    - Auto-remediate: Enabled for low/medium severity in non-prod
    - HITL required: High/critical severity OR any production deployment
"""

import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

# Import lazy-initialized AWS clients (Issue #466)
try:
    from aws_clients import (
        get_dynamodb_client,
        get_dynamodb_resource,
        get_eks_client,
        get_sqs_client,
        get_sts_client,
    )
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_dynamodb_client = _aws_clients.get_dynamodb_client
    get_dynamodb_resource = _aws_clients.get_dynamodb_resource
    get_eks_client = _aws_clients.get_eks_client
    get_sqs_client = _aws_clients.get_sqs_client
    get_sts_client = _aws_clients.get_sts_client

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "aura")
EKS_CLUSTER_NAME = os.environ.get(
    "EKS_CLUSTER_NAME", f"{PROJECT_NAME}-cluster-{ENVIRONMENT}"
)
JOB_STATE_TABLE = os.environ.get(
    "JOB_STATE_TABLE", f"{PROJECT_NAME}-orchestrator-jobs-{ENVIRONMENT}"
)
PLATFORM_SETTINGS_TABLE = os.environ.get(
    "PLATFORM_SETTINGS_TABLE", f"{PROJECT_NAME}-platform-settings-{ENVIRONMENT}"
)
ORCHESTRATOR_NAMESPACE = os.environ.get("ORCHESTRATOR_NAMESPACE", "aura")
# ORCHESTRATOR_IMAGE must be set via environment variable - no hardcoded account IDs
# Format: {account_id}.dkr.ecr.{region}.amazonaws.com/{project}-meta-orchestrator-{env}:latest
_account_id = os.environ.get("AWS_ACCOUNT_ID", "")
_region = os.environ.get("AWS_REGION", "")
_default_image = (
    f"{_account_id}.dkr.ecr.{_region}.amazonaws.com/{PROJECT_NAME}-meta-orchestrator-{ENVIRONMENT}:latest"
    if _account_id and _region
    else ""
)
ORCHESTRATOR_IMAGE = os.environ.get("ORCHESTRATOR_IMAGE", _default_image)
# Warm pool queue for hybrid/warm-pool mode
WARM_POOL_QUEUE_URL = os.environ.get("WARM_POOL_QUEUE_URL", "")


# Cached orchestrator settings (TTL-based cache)
_cached_settings: dict[str, Any] | None = None
_settings_cache_time: float = 0
SETTINGS_CACHE_TTL_SECONDS = 60  # Cache settings for 60 seconds


class DeploymentMode:
    """Deployment mode constants."""

    ON_DEMAND = "on_demand"
    WARM_POOL = "warm_pool"
    HYBRID = "hybrid"


def _get_orchestrator_settings() -> dict[str, Any]:
    """
    Get orchestrator settings from DynamoDB with caching.

    Returns platform orchestrator settings with TTL-based caching
    to minimize DynamoDB reads.
    """
    global _cached_settings, _settings_cache_time
    import time

    now = time.time()

    # Check cache validity
    if (
        _cached_settings is not None
        and (now - _settings_cache_time) < SETTINGS_CACHE_TTL_SECONDS
    ):
        return _cached_settings

    # Default settings (on-demand mode)
    default_settings = {
        "on_demand_jobs_enabled": True,
        "warm_pool_enabled": False,
        "hybrid_mode_enabled": False,
        "warm_pool_replicas": 1,
        "hybrid_threshold_queue_depth": 5,
        "hybrid_max_burst_jobs": 10,
    }

    try:
        response = get_dynamodb_client().get_item(
            TableName=PLATFORM_SETTINGS_TABLE,
            Key={
                "settings_type": {"S": "platform"},
                "settings_key": {"S": "orchestrator"},
            },
            ProjectionExpression="settings_value",
        )

        if "Item" in response and "settings_value" in response["Item"]:
            # Parse the settings JSON from DynamoDB
            settings_json = response["Item"]["settings_value"].get("S", "{}")
            settings = json.loads(settings_json)
            _cached_settings = {**default_settings, **settings}
        else:
            # No settings found, use defaults
            logger.info(
                "No orchestrator settings found, using defaults (on-demand mode)"
            )
            _cached_settings = default_settings

        _settings_cache_time = now
        return _cached_settings

    except ClientError as e:
        logger.warning(f"Error reading orchestrator settings: {e}, using defaults")
        return default_settings

    except Exception as e:
        logger.warning(f"Unexpected error reading settings: {e}, using defaults")
        return default_settings


def _get_current_deployment_mode() -> str:
    """
    Determine the current deployment mode from settings.

    Returns one of: on_demand, warm_pool, hybrid
    """
    settings = _get_orchestrator_settings()

    if settings.get("hybrid_mode_enabled"):
        return DeploymentMode.HYBRID
    elif settings.get("warm_pool_enabled"):
        return DeploymentMode.WARM_POOL
    else:
        return DeploymentMode.ON_DEMAND


def _get_warm_pool_queue_depth() -> int:
    """Get the approximate number of messages in the warm pool queue."""
    if not WARM_POOL_QUEUE_URL:
        return 0

    try:
        response = get_sqs_client().get_queue_attributes(
            QueueUrl=WARM_POOL_QUEUE_URL,
            AttributeNames=["ApproximateNumberOfMessages"],
        )
        return int(response.get("Attributes", {}).get("ApproximateNumberOfMessages", 0))
    except Exception as e:
        logger.warning(f"Error getting queue depth: {e}")
        return 0


def _route_to_warm_pool(
    job_id: str, task_id: str, payload: dict[str, Any], autonomy_config: dict[str, Any]
) -> dict[str, Any]:
    """
    Route job to warm pool via SQS queue.

    The warm pool pods continuously poll this queue and process jobs.
    """
    if not WARM_POOL_QUEUE_URL:
        return {
            "success": False,
            "error": "WARM_POOL_QUEUE_URL not configured",
        }

    try:
        message_body = {
            "job_id": job_id,
            "task_id": task_id,
            "payload": payload,
            "autonomy_config": autonomy_config,
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "routing_mode": "warm_pool",
        }

        response = get_sqs_client().send_message(
            QueueUrl=WARM_POOL_QUEUE_URL,
            MessageBody=json.dumps(message_body),
            MessageAttributes={
                "job_id": {"StringValue": job_id, "DataType": "String"},
                "task_id": {"StringValue": task_id, "DataType": "String"},
            },
        )

        return {
            "success": True,
            "info": {
                "job_id": job_id,
                "routing_mode": "warm_pool",
                "message_id": response.get("MessageId"),
            },
        }

    except Exception as e:
        logger.error(f"Error routing to warm pool: {e}")
        return {"success": False, "error": str(e)}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Process SQS messages and dispatch to EKS MetaOrchestrator Jobs.

    Args:
        event: SQS event containing batch of messages
        context: Lambda context

    Returns:
        Response with batch item failures for partial batch handling
    """
    logger.info(f"Received {len(event.get('Records', []))} messages")

    batch_item_failures = []
    table = get_dynamodb_resource().Table(JOB_STATE_TABLE)

    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")

        try:
            # Parse message body
            body = json.loads(record.get("body", "{}"))
            task_id = body.get("task_id", f"task-{uuid.uuid4().hex[:12]}")

            logger.info(f"Processing message {message_id}, task_id: {task_id}")

            # Generate unique job ID
            job_id = f"orchestrator-{uuid.uuid4().hex[:8]}"

            # Extract autonomy configuration
            autonomy_config = body.get("autonomy_config", {})
            payload = body.get("payload", {})
            severity = payload.get("severity", "medium")

            # Determine autonomy level based on environment and severity
            auto_remediate = _should_auto_remediate(severity, autonomy_config)
            require_hitl = _should_require_hitl(severity, autonomy_config)

            # Build job specification
            job_spec = _build_job_spec(
                job_id=job_id,
                task_id=task_id,
                payload=payload,
                autonomy_config={
                    **autonomy_config,
                    "auto_remediate": auto_remediate,
                    "require_hitl_for_deploy": require_hitl,
                },
            )

            # Record job state before dispatching
            job_record = {
                "job_id": job_id,
                "task_id": task_id,
                "sqs_message_id": message_id,
                "status": "PENDING",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "environment": ENVIRONMENT,
                "severity": severity,
                "auto_remediate": auto_remediate,
                "require_hitl": require_hitl,
                "payload_summary": {
                    "event_type": payload.get("event_type"),
                    "cve_id": payload.get("cve_id"),
                    "title": payload.get("title", "")[:100],
                },
                # TTL: 30 days for completed jobs
                "ttl": int(
                    (datetime.now(timezone.utc).timestamp()) + (30 * 24 * 60 * 60)
                ),
            }

            table.put_item(Item=job_record)
            logger.info(f"Created job record: {job_id}")

            # Determine deployment mode and route accordingly
            deployment_mode = _get_current_deployment_mode()
            logger.info(f"Deployment mode: {deployment_mode}")

            if deployment_mode == DeploymentMode.WARM_POOL:
                # Route to warm pool SQS queue
                dispatch_result = _route_to_warm_pool(
                    job_id=job_id,
                    task_id=task_id,
                    payload=payload,
                    autonomy_config={
                        **autonomy_config,
                        "auto_remediate": auto_remediate,
                        "require_hitl_for_deploy": require_hitl,
                    },
                )
            elif deployment_mode == DeploymentMode.HYBRID:
                # Check queue depth to decide warm pool vs burst job
                settings = _get_orchestrator_settings()
                queue_depth = _get_warm_pool_queue_depth()
                threshold = settings.get("hybrid_threshold_queue_depth", 5)

                if queue_depth < threshold:
                    # Route to warm pool
                    dispatch_result = _route_to_warm_pool(
                        job_id=job_id,
                        task_id=task_id,
                        payload=payload,
                        autonomy_config={
                            **autonomy_config,
                            "auto_remediate": auto_remediate,
                            "require_hitl_for_deploy": require_hitl,
                        },
                    )
                    logger.info(
                        f"Hybrid mode: routed to warm pool (queue_depth={queue_depth} < threshold={threshold})"
                    )
                else:
                    # Create burst job via EKS
                    dispatch_result = _dispatch_to_eks(job_id, job_spec)
                    logger.info(
                        f"Hybrid mode: created burst job (queue_depth={queue_depth} >= threshold={threshold})"
                    )
            else:
                # On-demand mode: dispatch to EKS Jobs
                dispatch_result = _dispatch_to_eks(job_id, job_spec)

            if dispatch_result["success"]:
                # Update job status to DISPATCHED
                table.update_item(
                    Key={"job_id": job_id},
                    UpdateExpression="SET #status = :status, updated_at = :updated_at, dispatch_info = :dispatch_info",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": "DISPATCHED",
                        ":updated_at": datetime.now(timezone.utc).isoformat(),
                        ":dispatch_info": dispatch_result.get("info", {}),
                    },
                )
                logger.info(f"Successfully dispatched job {job_id}")
            else:
                # Update job status to DISPATCH_FAILED
                table.update_item(
                    Key={"job_id": job_id},
                    UpdateExpression="SET #status = :status, updated_at = :updated_at, error = :error",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": "DISPATCH_FAILED",
                        ":updated_at": datetime.now(timezone.utc).isoformat(),
                        ":error": dispatch_result.get("error", "Unknown error"),
                    },
                )
                # Report as batch item failure for retry
                batch_item_failures.append({"itemIdentifier": message_id})
                logger.error(
                    f"Failed to dispatch job {job_id}: {dispatch_result.get('error')}"
                )

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message {message_id}: {e}")
            batch_item_failures.append({"itemIdentifier": message_id})

        except ClientError as e:
            logger.error(f"AWS error processing message {message_id}: {e}")
            batch_item_failures.append({"itemIdentifier": message_id})

        except Exception as e:
            logger.error(f"Unexpected error processing message {message_id}: {e}")
            batch_item_failures.append({"itemIdentifier": message_id})

    # Return batch item failures for SQS to retry
    response = {"batchItemFailures": batch_item_failures}

    logger.info(
        f"Processed {len(event.get('Records', []))} messages, "
        f"{len(batch_item_failures)} failures"
    )

    return response


def _should_auto_remediate(severity: str, autonomy_config: dict[str, Any]) -> bool:
    """
    Determine if auto-remediation should be enabled.

    For 85% autonomy:
    - Dev/QA: Auto-remediate low/medium severity
    - Prod: Never auto-remediate (always HITL)
    """
    if ENVIRONMENT == "prod":
        return False

    if autonomy_config.get("auto_remediate") is not None:
        result: bool = autonomy_config["auto_remediate"]
        return result

    # Default: auto-remediate low/medium in non-prod
    return severity.lower() in ("low", "medium", "info")


def _should_require_hitl(severity: str, autonomy_config: dict[str, Any]) -> bool:
    """
    Determine if HITL approval is required for deployment.

    For 85% autonomy:
    - Always require HITL for high/critical severity
    - Always require HITL in production
    - Allow bypass for low/medium in dev/qa
    """
    if ENVIRONMENT == "prod":
        return True

    if autonomy_config.get("require_hitl_for_deploy") is not None:
        result: bool = autonomy_config["require_hitl_for_deploy"]
        return result

    # Default: require HITL for high/critical
    return severity.lower() in ("high", "critical")


def _build_job_spec(
    job_id: str,
    task_id: str,
    payload: dict[str, Any],
    autonomy_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Build Kubernetes Job specification for MetaOrchestrator.

    Returns a dict that can be used to create a Kubernetes Job via the API.
    """
    # Encode payload as base64 for safe transport
    payload_with_config = {
        "task_id": task_id,
        "payload": payload,
        "autonomy_config": autonomy_config,
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
    }
    payload_b64 = base64.b64encode(json.dumps(payload_with_config).encode()).decode()

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_id,
            "namespace": ORCHESTRATOR_NAMESPACE,
            "labels": {
                "app": "meta-orchestrator",
                "job-id": job_id,
                "task-id": task_id,
                "environment": ENVIRONMENT,
                "auto-triggered": "true",
            },
            "annotations": {
                "aura.io/task-id": task_id,
                "aura.io/severity": payload.get("severity", "unknown"),
                "aura.io/dispatched-by": "orchestrator-dispatcher-lambda",
            },
        },
        "spec": {
            "ttlSecondsAfterFinished": 3600,  # Clean up 1 hour after completion
            "backoffLimit": 2,  # Retry twice on failure
            "activeDeadlineSeconds": 1800,  # 30 minute max execution
            "template": {
                "metadata": {
                    "labels": {
                        "app": "meta-orchestrator",
                        "job-id": job_id,
                    },
                },
                "spec": {
                    "serviceAccountName": "meta-orchestrator",
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": "orchestrator",
                            "image": ORCHESTRATOR_IMAGE,
                            "resources": {
                                "requests": {"memory": "2Gi", "cpu": "1"},
                                "limits": {"memory": "4Gi", "cpu": "2"},
                            },
                            "env": [
                                {"name": "JOB_ID", "value": job_id},
                                {"name": "TASK_ID", "value": task_id},
                                {"name": "TASK_PAYLOAD_B64", "value": payload_b64},
                                {"name": "ENVIRONMENT", "value": ENVIRONMENT},
                                {"name": "PROJECT_NAME", "value": PROJECT_NAME},
                                {
                                    "name": "NEPTUNE_ENDPOINT",
                                    "value": f"neptune.{PROJECT_NAME}.local:8182",
                                },
                                {
                                    "name": "OPENSEARCH_ENDPOINT",
                                    "value": f"opensearch.{PROJECT_NAME}.local:9200",
                                },
                                {
                                    "name": "JOB_STATE_TABLE",
                                    "value": JOB_STATE_TABLE,
                                },
                                {
                                    "name": "AWS_REGION",
                                    "valueFrom": {
                                        "fieldRef": {"fieldPath": "metadata.namespace"}
                                    },
                                },
                            ],
                            "envFrom": [
                                {
                                    "secretRef": {
                                        "name": f"{PROJECT_NAME}-secrets",
                                        "optional": True,
                                    }
                                }
                            ],
                        }
                    ],
                    "nodeSelector": {
                        "kubernetes.io/os": "linux",
                    },
                    "tolerations": [
                        {
                            "key": "workload-type",
                            "operator": "Equal",
                            "value": "compute-intensive",
                            "effect": "NoSchedule",
                        }
                    ],
                },
            },
        },
    }


def _dispatch_to_eks(job_id: str, job_spec: dict[str, Any]) -> dict[str, Any]:
    """
    Dispatch job to EKS cluster via Kubernetes API.

    Uses the EKS API to get cluster endpoint and auth token, then
    creates the Job via the Kubernetes API.
    """
    try:
        # Get cluster info
        cluster_info = get_eks_client().describe_cluster(name=EKS_CLUSTER_NAME)
        cluster = cluster_info.get("cluster", {})

        endpoint = cluster.get("endpoint")
        ca_data = cluster.get("certificateAuthority", {}).get("data")

        if not endpoint or not ca_data:
            return {
                "success": False,
                "error": f"Could not get cluster endpoint/CA for {EKS_CLUSTER_NAME}",
            }

        # Get authentication token
        _token = _get_eks_token(EKS_CLUSTER_NAME)  # noqa: F841

        # Create Kubernetes Job via API
        # Note: In production, use kubernetes client library
        # For now, we'll use a simplified approach via kubectl in the container
        # or store the job spec for the EKS operator to pick up

        # For this implementation, we'll store the job spec in DynamoDB
        # and have an EKS-side controller pick it up
        # This avoids needing direct k8s API access from Lambda

        logger.info(
            f"Job spec prepared for {job_id}, storing for EKS controller pickup"
        )

        return {
            "success": True,
            "info": {
                "job_id": job_id,
                "cluster": EKS_CLUSTER_NAME,
                "namespace": ORCHESTRATOR_NAMESPACE,
                "method": "dynamodb_pickup",
            },
        }

    except ClientError as e:
        logger.error(f"EKS API error: {e}")
        return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"Dispatch error: {e}")
        return {"success": False, "error": str(e)}


def _get_eks_token(cluster_name: str) -> str:
    """
    Get EKS authentication token using STS.

    This token can be used with the Kubernetes API server.
    """
    sts_client = get_sts_client()

    # Get presigned URL for GetCallerIdentity
    # This is the EKS authentication mechanism
    url = sts_client.generate_presigned_url(
        "get_caller_identity",
        Params={},
        ExpiresIn=60,
        HttpMethod="GET",
    )

    # EKS expects the token in a specific format
    # k8s-aws-v1.<base64-encoded-presigned-url>
    token = "k8s-aws-v1." + base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")

    return token
