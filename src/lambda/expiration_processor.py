"""
Project Aura - Expiration Processor Lambda

Scheduled Lambda function that processes expired HITL approval requests.
Triggered by CloudWatch Events Rule (hourly).

Implements auto-escalation for CRITICAL/HIGH severity and expiration for MEDIUM/LOW.
"""

import json
import logging
import os
from typing import Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import services (these will be available when deployed with proper packaging)
try:
    from src.services.hitl_approval_service import HITLApprovalService, HITLMode
    from src.services.notification_service import NotificationMode, NotificationService

    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False
    logger.warning("Services not available - using stub mode")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for expiration processing.

    This function is triggered by CloudWatch Events on an hourly schedule.
    It processes all pending approval requests and:
    - Sends warnings for requests approaching expiration
    - Escalates CRITICAL/HIGH severity expired requests
    - Marks MEDIUM/LOW severity expired requests as expired

    Args:
        event: CloudWatch Events scheduled event
        context: Lambda context

    Returns:
        Processing result summary
    """
    logger.info("Starting expiration processing")
    logger.info(f"Event: {json.dumps(event)}")

    # Get configuration from environment
    table_name = os.environ.get("HITL_TABLE_NAME")
    sns_topic_arn = os.environ.get("HITL_SNS_TOPIC_ARN")
    backup_reviewers_str = os.environ.get("BACKUP_REVIEWERS", "")
    timeout_hours = int(os.environ.get("TIMEOUT_HOURS", "24"))
    escalation_timeout_hours = int(os.environ.get("ESCALATION_TIMEOUT_HOURS", "12"))
    use_mock = os.environ.get("USE_MOCK", "false").lower() == "true"

    # Parse backup reviewers list
    backup_reviewers = [
        email.strip() for email in backup_reviewers_str.split(",") if email.strip()
    ]

    if not SERVICES_AVAILABLE:
        logger.error("Services not available - cannot process expirations")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "Services not available",
                    "processed": 0,
                }
            ),
        }

    try:
        # Initialize notification service
        notification_service = NotificationService(
            mode=NotificationMode.MOCK if use_mock else NotificationMode.AWS,
            sns_topic_arn=sns_topic_arn,
        )

        # Initialize HITL service with notification integration
        hitl_service = HITLApprovalService(
            mode=HITLMode.MOCK if use_mock else HITLMode.AWS,
            table_name=table_name,
            timeout_hours=timeout_hours,
            notification_service=notification_service,
            backup_reviewers=backup_reviewers,
            escalation_timeout_hours=escalation_timeout_hours,
        )

        # Process expirations
        result = hitl_service.process_expirations()

        # Build response
        response_body = {
            "processed": result.processed,
            "escalated": result.escalated,
            "expired": result.expired,
            "warnings_sent": result.warnings_sent,
            "errors": result.errors,
        }

        # Log CloudWatch metrics (optional - can be used for dashboards)
        logger.info(f"Processing complete: {json.dumps(response_body)}")

        # Return success response
        return {
            "statusCode": 200,
            "body": json.dumps(response_body),
        }

    except Exception as e:
        logger.error(f"Expiration processing failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": str(e),
                    "processed": 0,
                }
            ),
        }


# Local testing support
if __name__ == "__main__":
    # Set up local environment for testing
    os.environ["USE_MOCK"] = "true"
    os.environ["BACKUP_REVIEWERS"] = "backup1@example.com,backup2@example.com"
    os.environ["TIMEOUT_HOURS"] = "24"
    os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"

    # Simulate CloudWatch Events scheduled event
    test_event = {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "account": "123456789012",
        "time": "2025-12-01T12:00:00Z",
        "region": "us-east-1",
        "resources": [
            "arn:aws:events:us-east-1:123456789012:rule/aura-expiration-processor"
        ],
        "detail": {},
    }

    # Run handler
    result = handler(test_event, None)
    print(f"Result: {json.dumps(result, indent=2)}")
