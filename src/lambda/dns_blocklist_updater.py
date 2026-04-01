"""
Project Aura - DNS Blocklist Updater Lambda

Automatically updates DNS blocklists from threat intelligence feeds.
Triggered daily by CloudWatch Events or on-demand via API.

Pipeline:
1. Fetch threat intelligence from NVD, CISA, URLhaus, Abuse.ch
2. Generate dnsmasq blocklist configuration
3. Upload to S3 for ECS Fargate (Tier 2)
4. Update Kubernetes ConfigMap for EKS DaemonSet (Tier 1)
5. Send notification with update summary

Environment Variables:
- ENVIRONMENT: Environment name (dev, qa, prod)
- PROJECT_NAME: Project name for resource naming
- S3_BUCKET: S3 bucket for blocklist storage
- EKS_CLUSTER_NAME: EKS cluster name for ConfigMap updates
- SNS_TOPIC_ARN: SNS topic for notifications
- ENABLE_K8S_UPDATE: Enable Kubernetes ConfigMap updates (true/false)
"""

import asyncio
import json
import logging
import os

# Lambda runtime path adjustment
import sys
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

sys.path.insert(0, "/var/task")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import lazy-initialized AWS clients (Issue #466)
try:
    from aws_clients import get_eks_client, get_s3_client, get_sns_client
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_eks_client = _aws_clients.get_eks_client
    get_s3_client = _aws_clients.get_s3_client
    get_sns_client = _aws_clients.get_sns_client

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_env(key: str, default: str = "") -> str:
    """Get environment variable with default."""
    return os.environ.get(key, default)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda entry point for DNS blocklist updates.

    Args:
        event: Lambda event (CloudWatch Events scheduled or API Gateway)
        context: Lambda context

    Returns:
        Response with update status and statistics
    """
    logger.info(f"DNS Blocklist Updater triggered: {json.dumps(event)}")

    # Extract configuration
    environment = get_env("ENVIRONMENT", "dev")
    project_name = get_env("PROJECT_NAME", "aura")
    s3_bucket = get_env("S3_BUCKET", f"{project_name}-config-{environment}")
    sns_topic_arn = get_env("SNS_TOPIC_ARN", "")
    enable_k8s = get_env("ENABLE_K8S_UPDATE", "false").lower() == "true"

    # Check for force refresh flag
    force_refresh = event.get("force_refresh", False)
    dry_run = event.get("dry_run", False)

    try:
        # Run async blocklist generation
        result = asyncio.run(
            generate_and_deploy_blocklist(
                environment=environment,
                project_name=project_name,
                s3_bucket=s3_bucket,
                enable_k8s=enable_k8s,
                force_refresh=force_refresh,
                dry_run=dry_run,
            )
        )

        # Send notification
        if sns_topic_arn and not dry_run:
            send_notification(sns_topic_arn, result)

        logger.info(f"Blocklist update completed: {json.dumps(result)}")

        return {
            "statusCode": 200,
            "body": json.dumps(result),
            "headers": {"Content-Type": "application/json"},
        }

    except Exception as e:
        logger.error(f"Blocklist update failed: {e}", exc_info=True)

        error_result = {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Send error notification
        if sns_topic_arn:
            send_error_notification(sns_topic_arn, error_result)

        return {
            "statusCode": 500,
            "body": json.dumps(error_result),
            "headers": {"Content-Type": "application/json"},
        }


async def generate_and_deploy_blocklist(
    environment: str,
    project_name: str,
    s3_bucket: str,
    enable_k8s: bool,
    force_refresh: bool,
    dry_run: bool,
) -> dict[str, Any]:
    """
    Generate blocklist and deploy to infrastructure.

    Args:
        environment: Environment name
        project_name: Project name
        s3_bucket: S3 bucket for config storage
        enable_k8s: Enable Kubernetes ConfigMap updates
        force_refresh: Force refresh even if no changes
        dry_run: Don't actually deploy, just generate

    Returns:
        Result dictionary with status and statistics
    """
    # Import blocklist service (may not be available in Lambda without layer)
    try:
        from src.services.dns_blocklist_service import (
            BlocklistConfig,
            create_blocklist_service,
        )
    except ImportError:
        # Fallback for Lambda environment
        logger.warning("Blocklist service not available, using mock data")
        return await generate_mock_blocklist(dry_run)

    # Configure blocklist service
    config = BlocklistConfig(
        enable_nvd=True,
        enable_cisa_kev=True,
        enable_github=True,
        enable_urlhaus=True,
        enable_abuse_ch=True,
        min_severity="medium",
        block_ransomware=True,
        max_entries=10000,
        include_comments=True,
        include_metadata_header=True,
    )

    # Create service and generate blocklist
    service = create_blocklist_service(config=config, use_mock=False)

    logger.info("Generating blocklist from threat intelligence feeds...")
    entries = await service.generate_blocklist()
    stats = service.get_stats()

    # Render dnsmasq configuration
    dnsmasq_config = service.render_dnsmasq_config(entries)

    # Close threat client
    await service.threat_client.close()

    result = {
        "status": "success",
        "dry_run": dry_run,
        "environment": environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "statistics": stats,
        "config_size_bytes": len(dnsmasq_config.encode()),
    }

    if dry_run:
        result["message"] = "Dry run completed - no changes deployed"
        result["preview"] = dnsmasq_config[:500]
        return result

    # Deploy to S3 (Tier 2 - ECS Fargate)
    s3_key = f"dnsmasq/blocklist-{environment}.conf"
    s3_result = upload_to_s3(s3_bucket, s3_key, dnsmasq_config)
    result["s3_upload"] = s3_result

    # Deploy to Kubernetes ConfigMap (Tier 1 - EKS)
    if enable_k8s:
        k8s_result = await update_kubernetes_configmap(
            environment, project_name, dnsmasq_config
        )
        result["kubernetes_update"] = k8s_result

    result["message"] = f"Blocklist updated with {stats['total_entries']} entries"
    return result


async def generate_mock_blocklist(dry_run: bool) -> dict[str, Any]:
    """Generate mock blocklist when service is not available."""
    mock_entries = [
        "# Project Aura - Mock DNS Blocklist",
        "# Generated by Lambda (mock mode)",
        f"# Timestamp: {datetime.now(timezone.utc).isoformat()}",
        "",
        "# --- MALWARE ---",
        "address=/malware.test.com/0.0.0.0",
        "address=/dropper.evil.net/0.0.0.0",
        "",
        "# --- C2 ---",
        "address=/c2.botnet.io/0.0.0.0",
        "",
        "# --- PHISHING ---",
        "address=/phishing.fake.com/0.0.0.0",
    ]

    mock_config = "\n".join(mock_entries)

    return {
        "status": "success",
        "dry_run": dry_run,
        "mock_mode": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "statistics": {
            "total_entries": 4,
            "entries_by_source": {"mock": 4},
            "entries_by_category": {"malware": 2, "c2": 1, "phishing": 1},
        },
        "config_size_bytes": len(mock_config.encode()),
        "message": "Mock blocklist generated (blocklist service not available)",
    }


def upload_to_s3(bucket: str, key: str, content: str) -> dict[str, Any]:
    """
    Upload blocklist configuration to S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        content: Configuration content

    Returns:
        Upload result
    """
    try:
        # Add metadata
        metadata = {
            "generator": "aura-dns-blocklist-updater",
            "generated-at": datetime.now(timezone.utc).isoformat(),
            "content-type": "text/plain",
        }

        get_s3_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType="text/plain",
            Metadata=metadata,
        )

        logger.info(f"Uploaded blocklist to s3://{bucket}/{key}")

        return {
            "success": True,
            "bucket": bucket,
            "key": key,
            "size_bytes": len(content.encode()),
        }

    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def update_kubernetes_configmap(
    environment: str,
    project_name: str,
    config_content: str,
) -> dict[str, Any]:
    """
    Update Kubernetes ConfigMap with new blocklist.

    Uses kubectl via Lambda layer or EKS API.

    Args:
        environment: Environment name
        project_name: Project name
        config_content: dnsmasq configuration content

    Returns:
        Update result
    """
    # Note: In production, this would use the Kubernetes API
    # via the kubernetes Python client with EKS authentication.
    # For simplicity, we'll store in S3 and let a K8s CronJob sync it.

    logger.info("Kubernetes ConfigMap update requested")

    # Store in S3 for K8s sync job to pick up
    try:
        bucket = get_env("S3_BUCKET", f"{project_name}-config-{environment}")
        key = f"kubernetes/dnsmasq-blocklist-configmap-{environment}.conf"

        get_s3_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=config_content.encode("utf-8"),
            ContentType="text/plain",
            Metadata={
                "target-namespace": "aura-network-services",
                "target-configmap": "dnsmasq-blocklist",
            },
        )

        return {
            "success": True,
            "method": "s3-sync",
            "bucket": bucket,
            "key": key,
            "message": "ConfigMap content staged for K8s sync job",
        }

    except ClientError as e:
        logger.error(f"K8s ConfigMap staging failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def send_notification(topic_arn: str, result: dict[str, Any]) -> None:
    """Send success notification via SNS."""
    try:
        stats = result.get("statistics", {})
        total = stats.get("total_entries", 0)
        by_severity = stats.get("entries_by_severity", {})

        subject = f"[Aura] DNS Blocklist Updated - {total} entries"

        message = f"""DNS Blocklist Update Completed

Environment: {result.get('environment', 'unknown')}
Timestamp: {result.get('timestamp', 'unknown')}

Statistics:
- Total Entries: {total}
- Critical: {by_severity.get('critical', 0)}
- High: {by_severity.get('high', 0)}
- Medium: {by_severity.get('medium', 0)}
- Low: {by_severity.get('low', 0)}

Sources: {stats.get('entries_by_source', {})}
Categories: {stats.get('entries_by_category', {})}

Config Size: {result.get('config_size_bytes', 0)} bytes
Config Hash: {stats.get('config_hash', 'N/A')}

S3 Upload: {result.get('s3_upload', {}).get('success', 'N/A')}
K8s Update: {result.get('kubernetes_update', {}).get('success', 'N/A')}

---
Project Aura - Automated DNS Security
"""

        get_sns_client().publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message,
        )

        logger.info(f"Notification sent to {topic_arn}")

    except ClientError as e:
        logger.error(f"Failed to send notification: {e}")


def send_error_notification(topic_arn: str, result: dict[str, Any]) -> None:
    """Send error notification via SNS."""
    try:
        subject = "[Aura] DNS Blocklist Update FAILED"

        message = f"""DNS Blocklist Update Failed

Timestamp: {result.get('timestamp', 'unknown')}
Error: {result.get('error', 'Unknown error')}

Please investigate and retry manually if needed.

---
Project Aura - Automated DNS Security
"""

        get_sns_client().publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message,
        )

        logger.info(f"Error notification sent to {topic_arn}")

    except ClientError as e:
        logger.error(f"Failed to send error notification: {e}")


# For local testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_event = {
        "source": "local-test",
        "dry_run": True,
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
