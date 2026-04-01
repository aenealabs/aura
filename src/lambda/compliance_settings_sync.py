"""
Project Aura - Compliance Settings Sync Lambda

Syncs compliance settings from DynamoDB to SSM Parameter Store for use by
CloudFormation deployments. This enables runtime-configurable compliance
profiles that take effect on next deployment.

SSM Parameters Written:
- /aura/{env}/compliance/profile
- /aura/{env}/compliance/kms-mode
- /aura/{env}/compliance/log-retention-days
- /aura/{env}/compliance/audit-log-retention-days

Trigger: Invoked asynchronously by Settings API when compliance settings change.

ADR-040: Configurable Compliance Settings
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment configuration
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "aura")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")

# SSM parameter prefix
SSM_PREFIX = f"/{PROJECT_NAME}/{ENVIRONMENT}/compliance"

# Valid retention days (CloudWatch supported values)
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

# Valid compliance profiles
VALID_PROFILES = ["commercial", "cmmc_l1", "cmmc_l2", "govcloud"]

# Valid KMS modes
VALID_KMS_MODES = ["aws_managed", "customer_managed"]


def normalize_retention_days(days: int) -> int:
    """
    Normalize retention days to a valid CloudWatch value.

    CloudWatch only accepts specific retention values. This function
    finds the next valid value >= the requested days.

    Args:
        days: Requested retention days

    Returns:
        Valid CloudWatch retention days
    """
    if days in VALID_RETENTION_DAYS:
        return days

    for valid_days in VALID_RETENTION_DAYS:
        if valid_days >= days:
            return valid_days

    # Return maximum if requested exceeds all valid values
    return VALID_RETENTION_DAYS[-1]


def validate_event(event: dict[str, Any]) -> dict[str, Any]:
    """
    Validate and normalize the Lambda event payload.

    Args:
        event: Lambda event payload

    Returns:
        Validated and normalized settings

    Raises:
        ValueError: If validation fails
    """
    # Extract settings from event
    profile = event.get("profile", "commercial")
    kms_mode = event.get("kms_encryption_mode", "aws_managed")
    log_retention = event.get("log_retention_days", 90)
    audit_retention = event.get("audit_log_retention_days", 365)

    # Validate profile
    if profile not in VALID_PROFILES:
        raise ValueError(
            f"Invalid profile: {profile}. Must be one of: {VALID_PROFILES}"
        )

    # Validate KMS mode
    if kms_mode not in VALID_KMS_MODES:
        raise ValueError(
            f"Invalid KMS mode: {kms_mode}. Must be one of: {VALID_KMS_MODES}"
        )

    # Validate and normalize retention days
    if not isinstance(log_retention, int) or log_retention < 1:
        raise ValueError(f"Invalid log_retention_days: {log_retention}")

    if not isinstance(audit_retention, int) or audit_retention < 1:
        raise ValueError(f"Invalid audit_log_retention_days: {audit_retention}")

    # CMMC L2 and GovCloud require minimum 90-day retention
    if profile in ["cmmc_l2", "govcloud"] and log_retention < 90:
        logger.warning(
            f"Profile {profile} requires minimum 90-day retention. "
            f"Adjusting from {log_retention} to 90."
        )
        log_retention = 90

    return {
        "profile": profile,
        "kms_mode": kms_mode,
        "log_retention_days": normalize_retention_days(log_retention),
        "audit_log_retention_days": normalize_retention_days(audit_retention),
    }


def write_ssm_parameters(settings: dict[str, Any]) -> dict[str, Any]:
    """
    Write compliance settings to SSM Parameter Store.

    Args:
        settings: Validated compliance settings

    Returns:
        Summary of parameters written
    """
    ssm = boto3.client("ssm", region_name=AWS_REGION)

    parameters = {
        f"{SSM_PREFIX}/profile": settings["profile"],
        f"{SSM_PREFIX}/kms-mode": settings["kms_mode"],
        f"{SSM_PREFIX}/log-retention-days": str(settings["log_retention_days"]),
        f"{SSM_PREFIX}/audit-log-retention-days": str(
            settings["audit_log_retention_days"]
        ),
    }

    results: dict[str, list[Any]] = {
        "written": [],
        "failed": [],
    }

    for param_name, param_value in parameters.items():
        try:
            ssm.put_parameter(
                Name=param_name,
                Value=param_value,
                Type="String",
                Overwrite=True,
                Description=f"Compliance setting synced at {datetime.now(timezone.utc).isoformat()}",
                Tags=[
                    {"Key": "Project", "Value": PROJECT_NAME},
                    {"Key": "Environment", "Value": ENVIRONMENT},
                    {"Key": "ManagedBy", "Value": "compliance-settings-sync"},
                ],
            )
            results["written"].append(param_name)
            logger.info(f"Wrote SSM parameter: {param_name} = {param_value}")

        except ClientError as e:
            # Tags can't be updated on existing parameters, try without tags
            if "TagException" in str(e) or "ValidationException" in str(e):
                try:
                    ssm.put_parameter(
                        Name=param_name,
                        Value=param_value,
                        Type="String",
                        Overwrite=True,
                        Description=f"Compliance setting synced at {datetime.now(timezone.utc).isoformat()}",
                    )
                    results["written"].append(param_name)
                    logger.info(f"Wrote SSM parameter (no tags): {param_name}")
                except ClientError as e2:
                    results["failed"].append({"name": param_name, "error": str(e2)})
                    logger.error(f"Failed to write SSM parameter {param_name}: {e2}")
            else:
                results["failed"].append({"name": param_name, "error": str(e)})
                logger.error(f"Failed to write SSM parameter {param_name}: {e}")

    return results


def send_notification(settings: dict[str, Any], ssm_results: dict[str, Any]) -> bool:
    """
    Send SNS notification about compliance settings sync.

    Args:
        settings: Applied compliance settings
        ssm_results: Results of SSM parameter writes

    Returns:
        True if notification sent successfully
    """
    if not SNS_TOPIC_ARN:
        logger.info("No SNS topic configured, skipping notification")
        return False

    sns = boto3.client("sns", region_name=AWS_REGION)

    subject = f"[Aura {ENVIRONMENT.upper()}] Compliance Settings Synced"

    message = f"""
Compliance Settings Sync Complete
==================================

Environment: {ENVIRONMENT}
Timestamp: {datetime.now(timezone.utc).isoformat()}

Applied Settings:
- Profile: {settings['profile']}
- KMS Mode: {settings['kms_mode']}
- Log Retention: {settings['log_retention_days']} days
- Audit Log Retention: {settings['audit_log_retention_days']} days

SSM Parameters Updated: {len(ssm_results['written'])}
SSM Parameters Failed: {len(ssm_results['failed'])}

Next Steps:
- KMS mode changes will take effect on next infrastructure deployment
- Log retention is synced immediately by log-retention-sync Lambda

Note: If switching to customer-managed KMS, ensure the KMS key ARN is
configured in the infrastructure parameters before deploying.
"""

    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message,
        )
        logger.info(f"Sent notification to {SNS_TOPIC_ARN}")
        return True

    except ClientError as e:
        logger.error(f"Failed to send notification: {e}")
        return False


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for compliance settings sync.

    Writes compliance settings to SSM Parameter Store for use by
    CloudFormation during deployments.

    Args:
        event: Lambda event with compliance settings:
            - profile: Compliance profile (commercial/cmmc_l1/cmmc_l2/govcloud)
            - kms_encryption_mode: KMS mode (aws_managed/customer_managed)
            - log_retention_days: Log retention in days
            - audit_log_retention_days: Audit log retention in days
        context: Lambda context

    Returns:
        Summary of sync operation
    """
    logger.info(f"Compliance settings sync invoked with event: {json.dumps(event)}")

    start_time = datetime.now(timezone.utc)

    try:
        # Validate event payload
        settings = validate_event(event)
        logger.info(f"Validated settings: {settings}")

        # Write to SSM Parameter Store
        ssm_results = write_ssm_parameters(settings)

        # Send notification
        notification_sent = send_notification(settings, ssm_results)

        # Calculate duration
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        response_body: dict[str, Any] = {
            "status": "success",
            "environment": ENVIRONMENT,
            "settings_applied": settings,
            "ssm_parameters_written": len(ssm_results["written"]),
            "ssm_parameters_failed": len(ssm_results["failed"]),
            "notification_sent": notification_sent,
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if ssm_results["failed"]:
            response_body["failed_parameters"] = ssm_results["failed"]
            response_body["status"] = "partial_success"

        response = {
            "statusCode": 200,
            "body": response_body,
        }

        logger.info(
            f"Compliance settings sync complete: {json.dumps(response['body'])}"
        )
        return response

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return {
            "statusCode": 400,
            "body": {
                "status": "error",
                "error": str(e),
                "error_type": "validation_error",
            },
        }

    except Exception as e:
        logger.exception(f"Unexpected error during compliance settings sync: {e}")
        return {
            "statusCode": 500,
            "body": {
                "status": "error",
                "error": str(e),
                "error_type": "internal_error",
            },
        }


# For local testing
if __name__ == "__main__":
    test_event = {
        "profile": "cmmc_l2",
        "kms_encryption_mode": "customer_managed",
        "log_retention_days": 90,
        "audit_log_retention_days": 365,
    }

    result = handler(test_event, None)
    print(json.dumps(result, indent=2))
