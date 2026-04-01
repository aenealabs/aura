"""
Project Aura - Log Retention Sync Lambda

Automatically updates CloudWatch log group retention policies when
security settings change in the UI. Ensures compliance with
configurable retention policies (CMMC L2 requires 90+ days).

Trigger Methods:
1. Direct invocation from Settings API when retention changes
2. EventBridge rule on settings DynamoDB stream (future enhancement)

Environment Variables:
- ENVIRONMENT: Environment name (dev, qa, prod)
- PROJECT_NAME: Project name for resource naming (default: aura)
- LOG_GROUP_PREFIXES: Comma-separated prefixes to update (default: /aws/lambda/aura,/aws/codebuild/aura,/aura)
- SNS_TOPIC_ARN: SNS topic for notifications (optional)
- DRY_RUN: Set to 'true' to preview changes without applying (default: false)
"""

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
    from aws_clients import get_logs_client, get_sns_client
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_logs_client = _aws_clients.get_logs_client
    get_sns_client = _aws_clients.get_sns_client

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Valid retention values supported by CloudWatch Logs
VALID_RETENTION_DAYS = [
    1,
    3,
    5,
    7,
    14,
    30,
    60,
    90,
    120,
    150,
    180,
    365,
    400,
    545,
    731,
    1096,
    1827,
    2192,
    2557,
    2922,
    3288,
    3653,
]

# Default log group prefixes to update
DEFAULT_LOG_GROUP_PREFIXES = [
    "/aws/lambda/aura",
    "/aws/codebuild/aura",
    "/aura",
    "/aws/eks/aura",
    "/aws/ecs/aura",
]


def get_env(key: str, default: str = "") -> str:
    """Get environment variable with default."""
    return os.environ.get(key, default)


def validate_retention_days(days: int) -> int:
    """
    Validate and normalize retention days to CloudWatch-supported value.

    CloudWatch Logs only supports specific retention values.
    This function returns the closest valid value >= requested days.

    Args:
        days: Requested retention days

    Returns:
        Valid CloudWatch retention value
    """
    if days in VALID_RETENTION_DAYS:
        return days

    # Find the smallest valid value >= requested days
    for valid_days in VALID_RETENTION_DAYS:
        if valid_days >= days:
            logger.info(
                f"Normalized retention from {days} to {valid_days} days (CloudWatch constraint)"
            )
            return valid_days

    # If requested is larger than all valid values, use max
    return VALID_RETENTION_DAYS[-1]


def get_log_groups_by_prefix(prefix: str) -> list[dict]:
    """
    Get all log groups matching a prefix.

    Args:
        prefix: Log group name prefix

    Returns:
        List of log group details
    """
    log_groups = []
    paginator = get_logs_client().get_paginator("describe_log_groups")

    try:
        for page in paginator.paginate(logGroupNamePrefix=prefix):
            log_groups.extend(page.get("logGroups", []))
    except ClientError as e:
        logger.error(f"Failed to list log groups with prefix {prefix}: {e}")

    return log_groups


def update_log_group_retention(
    log_group_name: str, retention_days: int, dry_run: bool = False
) -> dict[str, Any]:
    """
    Update retention policy for a single log group.

    Args:
        log_group_name: Name of the log group
        retention_days: New retention period in days
        dry_run: If True, don't actually apply changes

    Returns:
        Result dictionary with status
    """
    result = {
        "logGroupName": log_group_name,
        "requestedRetention": retention_days,
        "success": False,
        "message": "",
    }

    try:
        # Get current retention
        response = get_logs_client().describe_log_groups(
            logGroupNamePrefix=log_group_name, limit=1
        )
        log_groups = response.get("logGroups", [])

        if not log_groups or log_groups[0]["logGroupName"] != log_group_name:
            result["message"] = "Log group not found"
            return result

        current_retention = log_groups[0].get("retentionInDays", "Never expires")
        result["currentRetention"] = current_retention

        # Check if update is needed
        if current_retention == retention_days:
            result["success"] = True
            result["message"] = "Already at requested retention"
            result["skipped"] = True
            return result

        if dry_run:
            result["success"] = True
            result["message"] = (
                f"DRY RUN: Would change from {current_retention} to {retention_days} days"
            )
            result["dryRun"] = True
            return result

        # Apply new retention
        get_logs_client().put_retention_policy(
            logGroupName=log_group_name, retentionInDays=retention_days
        )

        result["success"] = True
        result["message"] = f"Updated from {current_retention} to {retention_days} days"
        result["previousRetention"] = current_retention
        result["newRetention"] = retention_days

        logger.info(
            f"Updated {log_group_name}: {current_retention} -> {retention_days} days"
        )

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        result["message"] = f"Failed: {error_code} - {str(e)}"
        logger.error(f"Failed to update {log_group_name}: {e}")

    return result


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda entry point for log retention sync.

    Args:
        event: Lambda event containing retention_days and optional prefixes
            - retention_days: Required. New retention period (30, 60, 90, 180, 365)
            - prefixes: Optional. List of log group prefixes to update
            - dry_run: Optional. Preview changes without applying
        context: Lambda context

    Returns:
        Response with sync status and statistics
    """
    logger.info(f"Log Retention Sync triggered: {json.dumps(event)}")

    # Extract configuration
    environment = get_env("ENVIRONMENT", "dev")
    _project_name = get_env("PROJECT_NAME", "aura")  # noqa: F841
    sns_topic_arn = get_env("SNS_TOPIC_ARN", "")

    # Get retention days from event (required)
    retention_days = event.get("retention_days")
    if retention_days is None:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "status": "error",
                    "error": "retention_days is required",
                }
            ),
        }

    # Validate and normalize retention days
    retention_days = validate_retention_days(int(retention_days))

    # Get prefixes to update
    prefixes_env = get_env("LOG_GROUP_PREFIXES", "")
    if prefixes_env:
        default_prefixes = [p.strip() for p in prefixes_env.split(",") if p.strip()]
    else:
        default_prefixes = DEFAULT_LOG_GROUP_PREFIXES

    prefixes = event.get("prefixes", default_prefixes)

    # Check for dry run
    dry_run = event.get("dry_run", get_env("DRY_RUN", "false").lower() == "true")

    try:
        # Collect all log groups to update
        all_log_groups = []
        for prefix in prefixes:
            log_groups = get_log_groups_by_prefix(prefix)
            all_log_groups.extend(log_groups)
            logger.info(f"Found {len(log_groups)} log groups with prefix '{prefix}'")

        # Remove duplicates (in case prefixes overlap)
        seen_names = set()
        unique_log_groups = []
        for lg in all_log_groups:
            name = lg["logGroupName"]
            if name not in seen_names:
                seen_names.add(name)
                unique_log_groups.append(lg)

        logger.info(f"Processing {len(unique_log_groups)} unique log groups")

        # Update each log group
        results = []
        success_count = 0
        skipped_count = 0
        failed_count = 0

        for log_group in unique_log_groups:
            result = update_log_group_retention(
                log_group["logGroupName"], retention_days, dry_run
            )
            results.append(result)

            if result.get("success"):
                if result.get("skipped"):
                    skipped_count += 1
                else:
                    success_count += 1
            else:
                failed_count += 1

        # Build response
        timestamp = datetime.now(timezone.utc).isoformat()

        response_data = {
            "status": "success" if failed_count == 0 else "partial_success",
            "environment": environment,
            "timestamp": timestamp,
            "dry_run": dry_run,
            "retention_days": retention_days,
            "statistics": {
                "total_log_groups": len(unique_log_groups),
                "updated": success_count,
                "skipped": skipped_count,
                "failed": failed_count,
            },
            "prefixes_searched": prefixes,
        }

        # Include detailed results if not too many
        if len(results) <= 50:
            response_data["details"] = results
        else:
            # Just include failures and updates for large result sets
            response_data["details"] = [
                r for r in results if not r.get("skipped") or not r.get("success")
            ]

        # Send notification if configured
        if sns_topic_arn and not dry_run:
            send_notification(sns_topic_arn, response_data)

        logger.info(
            f"Log retention sync complete: {success_count} updated, "
            f"{skipped_count} skipped, {failed_count} failed"
        )

        return {
            "statusCode": 200,
            "body": json.dumps(response_data),
            "headers": {"Content-Type": "application/json"},
        }

    except Exception as e:
        logger.error(f"Log retention sync failed: {e}", exc_info=True)

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


def send_notification(topic_arn: str, result: dict[str, Any]) -> None:
    """Send success notification via SNS."""
    try:
        stats = result.get("statistics", {})
        retention = result.get("retention_days", "Unknown")

        subject = f"[Aura] Log Retention Updated to {retention} days"

        message = f"""Log Retention Sync Completed

Environment: {result.get('environment', 'unknown')}
Timestamp: {result.get('timestamp', 'unknown')}
Dry Run: {result.get('dry_run', False)}

New Retention: {retention} days

Statistics:
- Total Log Groups: {stats.get('total_log_groups', 0)}
- Updated: {stats.get('updated', 0)}
- Skipped (already at target): {stats.get('skipped', 0)}
- Failed: {stats.get('failed', 0)}

Prefixes Searched: {', '.join(result.get('prefixes_searched', []))}

---
Project Aura - Compliance Log Management
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
        subject = "[Aura] Log Retention Sync FAILED"

        message = f"""Log Retention Sync Failed

Timestamp: {result.get('timestamp', 'unknown')}
Error: {result.get('error', 'Unknown error')}

Please investigate and retry manually if needed.

---
Project Aura - Compliance Log Management
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
        "retention_days": 90,
        "dry_run": True,
        "prefixes": ["/aws/lambda/aura", "/aws/codebuild/aura"],
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result["body"]), indent=2))
