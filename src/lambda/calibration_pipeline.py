"""
Project Aura - Confidence Calibration Pipeline Lambda

Scheduled Lambda function that runs nightly to train calibration models.
Triggered by CloudWatch Events Rule (daily at 2 AM UTC).

Implements ADR-056: Documentation Agent - Phase 1.5 (Confidence Calibration)

Pipeline Stages:
1. Query DynamoDB for organization feedback records
2. Filter organizations with sufficient samples (≥100)
3. Train isotonic regression calibrators per organization
4. Store calibrator models in S3
5. Record calibration metrics to CloudWatch
6. Send notifications for calibration improvements

Environment Variables:
    ENVIRONMENT: Deployment environment (dev/qa/prod)
    PROJECT_NAME: Project name for resource naming
    S3_BUCKET: Bucket for calibrator model storage
    DYNAMODB_TABLE: DynamoDB table for feedback records
    SNS_TOPIC_ARN: SNS topic for notifications
    MIN_SAMPLES: Minimum samples for calibration (default: 100)
    USE_MOCK: Enable mock mode for testing
"""

import json
import logging
import os
import pickle
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import calibration services (available when deployed with proper packaging)
try:
    from sklearn.isotonic import IsotonicRegression

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("sklearn not available - calibration will use passthrough mode")


@dataclass
class CalibrationResult:
    """Result of calibration pipeline execution."""

    execution_id: str
    timestamp: str
    organizations_processed: int
    organizations_calibrated: int
    organizations_skipped: int
    total_feedback_records: int
    models_updated: int
    avg_ece_before: float
    avg_ece_after: float
    avg_improvement_percent: float
    errors: list[str] = field(default_factory=list)
    org_summaries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class OrganizationCalibration:
    """Calibration result for a single organization."""

    organization_id: str
    sample_count: int
    ece_before: float
    ece_after: float
    improvement_percent: float
    model_version: int
    calibrated: bool
    error: str | None = None


def calculate_ece(
    predicted: list[float], actual: list[float], n_bins: int = 10
) -> float:
    """
    Calculate Expected Calibration Error.

    ECE measures the average gap between predicted confidence and actual accuracy.
    Lower ECE = better calibrated model.

    Args:
        predicted: List of predicted confidence scores (0.0 to 1.0)
        actual: List of actual outcomes (0 or 1)
        n_bins: Number of bins for calibration calculation

    Returns:
        ECE value (0.0 = perfect calibration)
    """
    if not predicted or len(predicted) != len(actual):
        return 1.0

    n = len(predicted)
    if n == 0:
        return 1.0

    # Create bins
    bin_counts = [0] * n_bins
    bin_sums_predicted = [0.0] * n_bins
    bin_sums_actual = [0.0] * n_bins

    for p, a in zip(predicted, actual):
        # Find bin index
        bin_idx = min(int(p * n_bins), n_bins - 1)
        bin_counts[bin_idx] += 1
        bin_sums_predicted[bin_idx] += p
        bin_sums_actual[bin_idx] += a

    # Calculate ECE
    ece = 0.0
    for i in range(n_bins):
        if bin_counts[i] > 0:
            avg_predicted = bin_sums_predicted[i] / bin_counts[i]
            avg_actual = bin_sums_actual[i] / bin_counts[i]
            ece += (bin_counts[i] / n) * abs(avg_predicted - avg_actual)

    return ece


def query_feedback_by_organization(
    dynamodb_client: Any, table_name: str, organization_id: str
) -> list[dict[str, Any]]:
    """
    Query feedback records for an organization from DynamoDB.

    Args:
        dynamodb_client: Boto3 DynamoDB client
        table_name: DynamoDB table name
        organization_id: Organization ID to query

    Returns:
        List of feedback records
    """
    feedback_records = []

    try:
        # Query using GSI on organization_id
        paginator = dynamodb_client.get_paginator("query")

        for page in paginator.paginate(
            TableName=table_name,
            IndexName="organization-index",
            KeyConditionExpression="organization_id = :org_id",
            ExpressionAttributeValues={":org_id": {"S": organization_id}},
        ):
            for item in page.get("Items", []):
                record = {
                    "feedback_id": item.get("feedback_id", {}).get("S", ""),
                    "organization_id": item.get("organization_id", {}).get("S", ""),
                    "raw_confidence": float(
                        item.get("raw_confidence", {}).get("N", "0.5")
                    ),
                    "feedback_type": item.get("feedback_type", {}).get("S", ""),
                    "documentation_type": item.get("documentation_type", {}).get(
                        "S", ""
                    ),
                    "created_at": item.get("created_at", {}).get("S", ""),
                }
                feedback_records.append(record)

    except ClientError as e:
        logger.error(f"Error querying DynamoDB: {e}")
        raise

    return feedback_records


def list_organizations(dynamodb_client: Any, table_name: str) -> list[str]:
    """
    List all unique organization IDs with feedback records.

    Args:
        dynamodb_client: Boto3 DynamoDB client
        table_name: DynamoDB table name

    Returns:
        List of organization IDs
    """
    organizations = set()

    try:
        # Scan with projection for organization_id only
        paginator = dynamodb_client.get_paginator("scan")

        for page in paginator.paginate(
            TableName=table_name,
            ProjectionExpression="organization_id",
        ):
            for item in page.get("Items", []):
                org_id = item.get("organization_id", {}).get("S", "")
                if org_id:
                    organizations.add(org_id)

    except ClientError as e:
        logger.error(f"Error scanning DynamoDB: {e}")
        raise

    return list(organizations)


def train_calibrator(
    feedback_records: list[dict[str, Any]],
) -> tuple[Any | None, float, float]:
    """
    Train isotonic regression calibrator from feedback records.

    Args:
        feedback_records: List of feedback records

    Returns:
        Tuple of (calibrator, ece_before, ece_after)
    """
    if not SKLEARN_AVAILABLE:
        logger.warning("sklearn not available - returning passthrough")
        return None, 1.0, 1.0

    # Extract raw scores and outcomes
    raw_scores = []
    outcomes = []

    for record in feedback_records:
        raw_score = record.get("raw_confidence", 0.5)
        feedback_type = record.get("feedback_type", "").lower()

        # Map feedback to binary outcome
        if feedback_type == "accurate":
            outcome = 1.0
        elif feedback_type == "inaccurate":
            outcome = 0.0
        elif feedback_type == "partial":
            outcome = 0.5
        else:
            continue

        raw_scores.append(raw_score)
        outcomes.append(outcome)

    if len(raw_scores) < 2:
        logger.warning("Not enough records to train calibrator")
        return None, 1.0, 1.0

    # Calculate ECE before calibration
    ece_before = calculate_ece(raw_scores, outcomes)

    # Train isotonic regression
    calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    calibrator.fit(raw_scores, outcomes)

    # Calculate ECE after calibration
    calibrated_scores = calibrator.predict(raw_scores)
    ece_after = calculate_ece(calibrated_scores.tolist(), outcomes)

    return calibrator, ece_before, ece_after


def save_calibrator_to_s3(
    s3_client: Any,
    bucket: str,
    organization_id: str,
    calibrator: Any,
    model_version: int,
) -> bool:
    """
    Save calibrator model to S3.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        organization_id: Organization ID
        calibrator: Trained calibrator object
        model_version: Version number for the model

    Returns:
        True if successful
    """
    try:
        key = f"calibration-models/{organization_id}/calibrator_v{model_version}.pkl"

        # Serialize calibrator
        calibrator_bytes = pickle.dumps(calibrator)

        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=calibrator_bytes,
            ContentType="application/octet-stream",
            Metadata={
                "organization_id": organization_id,
                "model_version": str(model_version),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Also save as "latest" for easy access
        latest_key = f"calibration-models/{organization_id}/calibrator_latest.pkl"
        s3_client.put_object(
            Bucket=bucket,
            Key=latest_key,
            Body=calibrator_bytes,
            ContentType="application/octet-stream",
            Metadata={
                "organization_id": organization_id,
                "model_version": str(model_version),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(f"Saved calibrator to s3://{bucket}/{key}")
        return True

    except ClientError as e:
        logger.error(f"Error saving calibrator to S3: {e}")
        return False


def get_current_model_version(s3_client: Any, bucket: str, organization_id: str) -> int:
    """
    Get the current model version for an organization.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        organization_id: Organization ID

    Returns:
        Current version number (0 if no previous model)
    """
    try:
        key = f"calibration-models/{organization_id}/calibrator_latest.pkl"
        response = s3_client.head_object(Bucket=bucket, Key=key)
        version_str = response.get("Metadata", {}).get("model_version", "0")
        return int(version_str)

    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return 0
        logger.error(f"Error getting model version: {e}")
        return 0


def record_cloudwatch_metrics(
    cloudwatch_client: Any,
    namespace: str,
    organization_id: str,
    ece_before: float,
    ece_after: float,
    sample_count: int,
) -> None:
    """
    Record calibration metrics to CloudWatch.

    Args:
        cloudwatch_client: Boto3 CloudWatch client
        namespace: CloudWatch namespace
        organization_id: Organization ID
        ece_before: ECE before calibration
        ece_after: ECE after calibration
        sample_count: Number of samples used
    """
    try:
        timestamp = datetime.now(timezone.utc)
        metrics = [
            {
                "MetricName": "ECEBeforeCalibration",
                "Dimensions": [
                    {"Name": "OrganizationId", "Value": organization_id},
                ],
                "Timestamp": timestamp,
                "Value": ece_before,
                "Unit": "None",
            },
            {
                "MetricName": "ECEAfterCalibration",
                "Dimensions": [
                    {"Name": "OrganizationId", "Value": organization_id},
                ],
                "Timestamp": timestamp,
                "Value": ece_after,
                "Unit": "None",
            },
            {
                "MetricName": "CalibrationSampleCount",
                "Dimensions": [
                    {"Name": "OrganizationId", "Value": organization_id},
                ],
                "Timestamp": timestamp,
                "Value": sample_count,
                "Unit": "Count",
            },
        ]

        # Calculate improvement
        if ece_before > 0:
            improvement = ((ece_before - ece_after) / ece_before) * 100
            metrics.append(
                {
                    "MetricName": "ECEImprovementPercent",
                    "Dimensions": [
                        {"Name": "OrganizationId", "Value": organization_id},
                    ],
                    "Timestamp": timestamp,
                    "Value": improvement,
                    "Unit": "Percent",
                }
            )

        cloudwatch_client.put_metric_data(Namespace=namespace, MetricData=metrics)
        logger.info(f"Recorded CloudWatch metrics for {organization_id}")

    except ClientError as e:
        logger.error(f"Error recording CloudWatch metrics: {e}")


def send_notification(
    sns_client: Any, topic_arn: str, result: CalibrationResult
) -> None:
    """
    Send SNS notification about calibration results.

    Args:
        sns_client: Boto3 SNS client
        topic_arn: SNS topic ARN
        result: Calibration result
    """
    if not topic_arn:
        return

    try:
        subject = f"[Aura] Confidence Calibration Complete - {result.organizations_calibrated} orgs updated"

        message = f"""Confidence Calibration Pipeline Complete

Execution ID: {result.execution_id}
Timestamp: {result.timestamp}

Summary:
- Organizations processed: {result.organizations_processed}
- Organizations calibrated: {result.organizations_calibrated}
- Organizations skipped: {result.organizations_skipped}
- Total feedback records: {result.total_feedback_records}
- Models updated: {result.models_updated}

Calibration Quality:
- Average ECE before: {result.avg_ece_before:.4f}
- Average ECE after: {result.avg_ece_after:.4f}
- Average improvement: {result.avg_improvement_percent:.1f}%

"""

        if result.errors:
            message += f"\nErrors ({len(result.errors)}):\n"
            for error in result.errors[:5]:  # Limit to 5 errors
                message += f"  - {error}\n"

        message += """
---
Project Aura - Documentation Agent Calibration Pipeline
"""

        sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject[:100],  # SNS subject limit
            Message=message,
        )
        logger.info("Sent SNS notification")

    except ClientError as e:
        logger.error(f"Error sending SNS notification: {e}")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for nightly calibration pipeline.

    This function is triggered by CloudWatch Events daily at 2 AM UTC.
    It trains calibration models for all organizations with sufficient feedback.

    Args:
        event: CloudWatch Events scheduled event
        context: Lambda context

    Returns:
        Pipeline execution result summary
    """
    logger.info("Starting confidence calibration pipeline")
    logger.info(f"Event: {json.dumps(event)}")

    # Generate execution ID
    execution_id = f"calibration-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Get configuration from environment
    environment = os.environ.get("ENVIRONMENT", "dev")
    project_name = os.environ.get("PROJECT_NAME", "aura")
    s3_bucket = os.environ.get("S3_BUCKET", f"{project_name}-calibration-{environment}")
    dynamodb_table = os.environ.get(
        "DYNAMODB_TABLE", f"{project_name}-documentation-feedback-{environment}"
    )
    sns_topic_arn = os.environ.get("SNS_TOPIC_ARN", "")
    min_samples = int(os.environ.get("MIN_SAMPLES", "100"))
    use_mock = os.environ.get("USE_MOCK", "false").lower() == "true"
    cloudwatch_namespace = f"{project_name.title()}/DocumentationCalibration"

    # Initialize result
    result = CalibrationResult(
        execution_id=execution_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        organizations_processed=0,
        organizations_calibrated=0,
        organizations_skipped=0,
        total_feedback_records=0,
        models_updated=0,
        avg_ece_before=0.0,
        avg_ece_after=0.0,
        avg_improvement_percent=0.0,
    )

    if use_mock:
        logger.info("Running in mock mode")
        result.organizations_processed = 3
        result.organizations_calibrated = 2
        result.organizations_skipped = 1
        result.total_feedback_records = 350
        result.models_updated = 2
        result.avg_ece_before = 0.25
        result.avg_ece_after = 0.08
        result.avg_improvement_percent = 68.0
        result.org_summaries = [
            {
                "organization_id": "org-001",
                "sample_count": 150,
                "calibrated": True,
                "improvement": 65.0,
            },
            {
                "organization_id": "org-002",
                "sample_count": 200,
                "calibrated": True,
                "improvement": 71.0,
            },
            {
                "organization_id": "org-003",
                "sample_count": 50,
                "calibrated": False,
                "reason": "Insufficient samples",
            },
        ]

        return {
            "statusCode": 200,
            "body": json.dumps(result.to_dict()),
        }

    # Initialize AWS clients
    dynamodb_client = boto3.client("dynamodb")
    s3_client = boto3.client("s3")
    cloudwatch_client = boto3.client("cloudwatch")
    sns_client = boto3.client("sns")

    try:
        # List all organizations with feedback
        logger.info("Stage 1: Listing organizations with feedback...")
        organizations = list_organizations(dynamodb_client, dynamodb_table)
        result.organizations_processed = len(organizations)
        logger.info(f"Found {len(organizations)} organizations")

        # Track calibration quality for averaging
        ece_before_values = []
        ece_after_values = []
        improvement_values = []

        # Process each organization
        for org_id in organizations:
            logger.info(f"Processing organization: {org_id}")

            try:
                # Query feedback records
                feedback_records = query_feedback_by_organization(
                    dynamodb_client, dynamodb_table, org_id
                )
                sample_count = len(feedback_records)
                result.total_feedback_records += sample_count

                # Check minimum samples
                if sample_count < min_samples:
                    logger.info(
                        f"Skipping {org_id}: {sample_count} samples < {min_samples} minimum"
                    )
                    result.organizations_skipped += 1
                    result.org_summaries.append(
                        {
                            "organization_id": org_id,
                            "sample_count": sample_count,
                            "calibrated": False,
                            "reason": f"Insufficient samples ({sample_count}/{min_samples})",
                        }
                    )
                    continue

                # Train calibrator
                logger.info(
                    f"Training calibrator for {org_id} with {sample_count} samples"
                )
                calibrator, ece_before, ece_after = train_calibrator(feedback_records)

                if calibrator is None:
                    logger.warning(f"Could not train calibrator for {org_id}")
                    result.organizations_skipped += 1
                    result.org_summaries.append(
                        {
                            "organization_id": org_id,
                            "sample_count": sample_count,
                            "calibrated": False,
                            "reason": "Training failed",
                        }
                    )
                    continue

                # Get current version and increment
                current_version = get_current_model_version(
                    s3_client, s3_bucket, org_id
                )
                new_version = current_version + 1

                # Save calibrator to S3
                if save_calibrator_to_s3(
                    s3_client, s3_bucket, org_id, calibrator, new_version
                ):
                    result.models_updated += 1

                # Record metrics to CloudWatch
                record_cloudwatch_metrics(
                    cloudwatch_client,
                    cloudwatch_namespace,
                    org_id,
                    ece_before,
                    ece_after,
                    sample_count,
                )

                # Calculate improvement
                improvement = 0.0
                if ece_before > 0:
                    improvement = ((ece_before - ece_after) / ece_before) * 100

                ece_before_values.append(ece_before)
                ece_after_values.append(ece_after)
                improvement_values.append(improvement)

                result.organizations_calibrated += 1
                result.org_summaries.append(
                    {
                        "organization_id": org_id,
                        "sample_count": sample_count,
                        "calibrated": True,
                        "ece_before": round(ece_before, 4),
                        "ece_after": round(ece_after, 4),
                        "improvement": round(improvement, 1),
                        "model_version": new_version,
                    }
                )

                logger.info(
                    f"Calibrated {org_id}: ECE {ece_before:.4f} -> {ece_after:.4f} "
                    f"({improvement:.1f}% improvement)"
                )

            except Exception as e:
                error_msg = f"Error processing {org_id}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                result.organizations_skipped += 1

        # Calculate averages
        if ece_before_values:
            result.avg_ece_before = sum(ece_before_values) / len(ece_before_values)
            result.avg_ece_after = sum(ece_after_values) / len(ece_after_values)
            result.avg_improvement_percent = sum(improvement_values) / len(
                improvement_values
            )

        # Send notification
        if sns_topic_arn and result.organizations_calibrated > 0:
            send_notification(sns_client, sns_topic_arn, result)

        # Log summary
        logger.info(f"Pipeline complete: {json.dumps(result.to_dict())}")

        return {
            "statusCode": 200,
            "body": json.dumps(result.to_dict()),
        }

    except Exception as e:
        logger.error(f"Calibration pipeline failed: {e}")
        result.errors.append(str(e))
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": str(e),
                    "execution_id": execution_id,
                    "partial_result": result.to_dict(),
                }
            ),
        }


# Local testing support
if __name__ == "__main__":
    # Set up local environment for testing
    os.environ["USE_MOCK"] = "true"
    os.environ["ENVIRONMENT"] = "dev"
    os.environ["MIN_SAMPLES"] = "100"

    # Simulate CloudWatch Events scheduled event
    test_event = {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "account": "123456789012",
        "time": "2025-01-06T02:00:00Z",
        "region": "us-east-1",
        "resources": [
            "arn:aws:events:us-east-1:123456789012:rule/aura-calibration-pipeline"
        ],
        "detail": {},
    }

    # Run handler
    result = handler(test_event, None)
    print(f"Result: {json.dumps(json.loads(result['body']), indent=2)}")
