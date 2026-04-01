"""Lambda handler for scheduled drift detection (ADR-062).

Triggered by EventBridge rule every 6 hours to detect configuration drift
in Kubernetes resources and report via CloudWatch metrics and SNS alerts.
"""

import json
import logging
import os
from datetime import datetime

import boto3

from src.services.env_validator.baseline_manager import BaselineManager
from src.services.env_validator.drift_detector import DriftDetector

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment configuration
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
SNS_TOPIC_ARN = os.environ.get("DRIFT_SNS_TOPIC_ARN", "")
CLOUDWATCH_NAMESPACE = os.environ.get("CLOUDWATCH_NAMESPACE", "Aura/EnvValidator")
EKS_CLUSTER_NAME = os.environ.get("EKS_CLUSTER_NAME", f"aura-cluster-{ENVIRONMENT}")


def get_k8s_manifests() -> str:
    """Fetch current Kubernetes manifests from the cluster.

    Uses kubectl via EKS API to get ConfigMaps, Deployments, and ServiceAccounts
    from the aura-system and default namespaces.

    Returns:
        YAML string of all relevant resources
    """
    # For Lambda execution, we use boto3 to interact with EKS
    # In production, this would use the EKS API or a sidecar
    # For now, we fetch from a known S3 location where manifests are stored
    s3 = boto3.client("s3")
    bucket = os.environ.get(
        "MANIFEST_BUCKET",
        f"aura-application-artifacts-{os.environ.get('AWS_ACCOUNT_ID', '')}-{ENVIRONMENT}",
    )

    try:
        # Try to get the latest deployed manifests from S3
        response = s3.get_object(
            Bucket=bucket, Key=f"manifests/{ENVIRONMENT}/current-state.yaml"
        )
        return response["Body"].read().decode("utf-8")
    except s3.exceptions.NoSuchKey:
        logger.warning("No manifest state file found, using empty manifest")
        return ""
    except Exception as e:
        logger.error(f"Failed to fetch manifests from S3: {e}")
        return ""


def publish_metrics(drift_report) -> None:
    """Publish drift detection metrics to CloudWatch.

    Args:
        drift_report: DriftReport from drift detector
    """
    cloudwatch = boto3.client("cloudwatch")

    metrics = [
        {
            "MetricName": "DriftDetectionRuns",
            "Value": 1,
            "Unit": "Count",
            "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
        },
        {
            "MetricName": "ResourcesChecked",
            "Value": drift_report.resources_checked,
            "Unit": "Count",
            "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
        },
        {
            "MetricName": "DriftEventsDetected",
            "Value": len(drift_report.drift_events),
            "Unit": "Count",
            "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
        },
        {
            "MetricName": "CriticalDriftEvents",
            "Value": drift_report.critical_drift_count,
            "Unit": "Count",
            "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
        },
    ]

    # Add metric for drift detected (for alarm)
    if drift_report.has_drift:
        metrics.append(
            {
                "MetricName": "DriftDetected",
                "Value": 1,
                "Unit": "Count",
                "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
            }
        )

    try:
        cloudwatch.put_metric_data(Namespace=CLOUDWATCH_NAMESPACE, MetricData=metrics)
        logger.info(f"Published {len(metrics)} metrics to CloudWatch")
    except Exception as e:
        logger.error(f"Failed to publish CloudWatch metrics: {e}")


def send_sns_alert(drift_report) -> None:
    """Send SNS alert for critical drift events.

    Args:
        drift_report: DriftReport from drift detector
    """
    if not SNS_TOPIC_ARN:
        logger.warning("SNS_TOPIC_ARN not configured, skipping alert")
        return

    if not drift_report.has_drift:
        return

    sns = boto3.client("sns")

    # Build alert message
    critical_events = [
        e for e in drift_report.drift_events if e.severity.value == "critical"
    ]

    subject = f"[{ENVIRONMENT.upper()}] Configuration Drift Detected"
    if critical_events:
        subject = f"[{ENVIRONMENT.upper()}] CRITICAL Configuration Drift Detected"

    message = {
        "environment": ENVIRONMENT,
        "timestamp": drift_report.timestamp.isoformat(),
        "run_id": drift_report.run_id,
        "summary": {
            "resources_checked": drift_report.resources_checked,
            "total_drift_events": len(drift_report.drift_events),
            "critical_drift_events": len(critical_events),
        },
        "drift_events": [
            {
                "resource": f"{e.resource_type}/{e.resource_name}",
                "namespace": e.namespace,
                "field": e.field_path,
                "severity": e.severity.value,
                "baseline": e.baseline_value[:100],  # Truncate for readability
                "current": e.current_value[:100],
            }
            for e in drift_report.drift_events[:10]  # Limit to first 10
        ],
    }

    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject[:100],  # SNS subject limit
            Message=json.dumps(message, indent=2),
            MessageAttributes={
                "environment": {"DataType": "String", "StringValue": ENVIRONMENT},
                "severity": {
                    "DataType": "String",
                    "StringValue": "critical" if critical_events else "warning",
                },
            },
        )
        logger.info(f"Sent SNS alert to {SNS_TOPIC_ARN}")
    except Exception as e:
        logger.error(f"Failed to send SNS alert: {e}")


def lambda_handler(event, context):
    """Lambda handler for scheduled drift detection.

    Args:
        event: EventBridge scheduled event
        context: Lambda context

    Returns:
        Dict with execution status and summary
    """
    logger.info(f"Starting drift detection for environment: {ENVIRONMENT}")
    logger.info(f"Event: {json.dumps(event)}")

    start_time = datetime.utcnow()

    # Initialize baseline manager and drift detector
    baseline_manager = BaselineManager(ENVIRONMENT)
    drift_detector = DriftDetector(ENVIRONMENT, baseline_manager)

    # Get current manifests
    manifest_yaml = get_k8s_manifests()

    if not manifest_yaml:
        logger.warning("No manifests to check, exiting")
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "skipped",
                    "reason": "no_manifests",
                    "environment": ENVIRONMENT,
                }
            ),
        }

    # Run drift detection
    drift_report = drift_detector.detect_drift(manifest_yaml)

    # Save drift events to history
    for drift_event in drift_report.drift_events:
        baseline_manager.save_drift_event(drift_event)

    # Publish metrics
    publish_metrics(drift_report)

    # Send SNS alert if drift detected
    if drift_report.has_drift:
        send_sns_alert(drift_report)

    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

    result = {
        "statusCode": 200,
        "body": json.dumps(
            {
                "status": "completed",
                "environment": ENVIRONMENT,
                "run_id": drift_report.run_id,
                "resources_checked": drift_report.resources_checked,
                "drift_detected": drift_report.has_drift,
                "drift_events": len(drift_report.drift_events),
                "critical_drift": drift_report.critical_drift_count,
                "duration_ms": round(duration_ms, 2),
                "timestamp": drift_report.timestamp.isoformat(),
            }
        ),
    }

    logger.info(f"Drift detection completed: {result['body']}")
    return result
