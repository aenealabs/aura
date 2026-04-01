"""Pytest fixtures for GPU Scheduler tests."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJob,
    GPUJobCreateRequest,
    GPUJobPriority,
    GPUJobStatus,
    GPUJobTemplate,
    GPUJobType,
    GPUQuota,
    GPUScheduledJob,
    ScheduleCreateRequest,
    ScheduledJobStatus,
    ScheduleFrequency,
    TemplateCreateRequest,
)

# Test constants
AWS_REGION = "us-east-1"
TEST_ACCOUNT_ID = "123456789012"
TEST_ENV = "test"


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Set test environment variables."""
    env_vars = {
        "AWS_REGION": AWS_REGION,
        "AWS_ACCOUNT_ID": TEST_ACCOUNT_ID,
        "ENVIRONMENT": TEST_ENV,
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
    }
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def mock_dynamodb() -> Generator[dict[str, Any], None, None]:
    """Create mock DynamoDB with GPU tables."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name=AWS_REGION)
        resource = boto3.resource("dynamodb", region_name=AWS_REGION)

        # Create GPU jobs table
        client.create_table(
            TableName=f"aura-gpu-jobs-{TEST_ENV}",
            KeySchema=[
                {"AttributeName": "organization_id", "KeyType": "HASH"},
                {"AttributeName": "job_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "organization_id", "AttributeType": "S"},
                {"AttributeName": "job_id", "AttributeType": "S"},
                {"AttributeName": "org_status", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "org-status-index",
                    "KeySchema": [
                        {"AttributeName": "org_status", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "user-created-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create GPU quotas table
        client.create_table(
            TableName=f"aura-gpu-quotas-{TEST_ENV}",
            KeySchema=[
                {"AttributeName": "organization_id", "KeyType": "HASH"},
                {"AttributeName": "quota_type", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "organization_id", "AttributeType": "S"},
                {"AttributeName": "quota_type", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create GPU templates table (Phase 5)
        client.create_table(
            TableName=f"aura-gpu-templates-{TEST_ENV}",
            KeySchema=[
                {"AttributeName": "organization_id", "KeyType": "HASH"},
                {"AttributeName": "template_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "organization_id", "AttributeType": "S"},
                {"AttributeName": "template_id", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user-templates-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create GPU schedules table (Phase 5)
        client.create_table(
            TableName=f"aura-gpu-schedules-{TEST_ENV}",
            KeySchema=[
                {"AttributeName": "organization_id", "KeyType": "HASH"},
                {"AttributeName": "schedule_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "organization_id", "AttributeType": "S"},
                {"AttributeName": "schedule_id", "AttributeType": "S"},
                {"AttributeName": "status_next_run", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "status-next-run-index",
                    "KeySchema": [
                        {"AttributeName": "organization_id", "KeyType": "HASH"},
                        {"AttributeName": "status_next_run", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield {
            "client": client,
            "resource": resource,
            "jobs_table": resource.Table(f"aura-gpu-jobs-{TEST_ENV}"),
            "quotas_table": resource.Table(f"aura-gpu-quotas-{TEST_ENV}"),
            "templates_table": resource.Table(f"aura-gpu-templates-{TEST_ENV}"),
            "schedules_table": resource.Table(f"aura-gpu-schedules-{TEST_ENV}"),
        }


@pytest.fixture
def mock_sqs() -> Generator[dict[str, Any], None, None]:
    """Create mock SQS with GPU jobs queue."""
    with mock_aws():
        client = boto3.client("sqs", region_name=AWS_REGION)

        # Create FIFO queue
        response = client.create_queue(
            QueueName=f"aura-gpu-jobs-queue-{TEST_ENV}.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "false",
            },
        )

        yield {
            "client": client,
            "queue_url": response["QueueUrl"],
        }


@pytest.fixture
def mock_s3() -> Generator[dict[str, Any], None, None]:
    """Create mock S3 with checkpoints bucket."""
    with mock_aws():
        client = boto3.client("s3", region_name=AWS_REGION)

        bucket_name = f"aura-gpu-checkpoints-{TEST_ACCOUNT_ID}-{TEST_ENV}"
        client.create_bucket(Bucket=bucket_name)

        yield {
            "client": client,
            "bucket_name": bucket_name,
        }


@pytest.fixture
def mock_aws_services(
    mock_dynamodb: dict[str, Any],
    mock_sqs: dict[str, Any],
    mock_s3: dict[str, Any],
) -> dict[str, Any]:
    """Combined AWS service mocks."""
    return {
        **mock_dynamodb,
        **mock_sqs,
        **mock_s3,
    }


@pytest.fixture
def gpu_scheduler_service(mock_aws_services: dict[str, Any]):
    """Create GPU scheduler service with mocked AWS."""
    from src.services.gpu_scheduler.gpu_scheduler_service import GPUSchedulerService

    service = GPUSchedulerService(
        jobs_table_name=f"aura-gpu-jobs-{TEST_ENV}",
        quotas_table_name=f"aura-gpu-quotas-{TEST_ENV}",
        queue_url=mock_aws_services["queue_url"],
        checkpoints_bucket=mock_aws_services["bucket_name"],
        region=AWS_REGION,
    )
    return service


@pytest.fixture
def sample_embedding_config() -> EmbeddingJobConfig:
    """Create sample embedding job configuration."""
    return EmbeddingJobConfig(
        repository_id="test-repo-123",
        branch="main",
        model="codebert-base",
        batch_size=32,
    )


@pytest.fixture
def sample_job_request(
    sample_embedding_config: EmbeddingJobConfig,
) -> GPUJobCreateRequest:
    """Create sample job creation request."""
    return GPUJobCreateRequest(
        job_type=GPUJobType.EMBEDDING_GENERATION,
        config=sample_embedding_config,
        priority=GPUJobPriority.NORMAL,
        gpu_memory_gb=8,
        max_runtime_hours=2,
        checkpoint_enabled=True,
    )


@pytest.fixture
def sample_gpu_job(sample_embedding_config: EmbeddingJobConfig) -> GPUJob:
    """Create sample GPU job."""
    return GPUJob(
        job_id="job-12345678",
        organization_id="org-test-123",
        user_id="user-test-456",
        job_type=GPUJobType.EMBEDDING_GENERATION,
        status=GPUJobStatus.QUEUED,
        priority=GPUJobPriority.NORMAL,
        config=sample_embedding_config,
        gpu_memory_gb=8,
        max_runtime_hours=2,
        checkpoint_enabled=True,
        checkpoint_s3_path="s3://bucket/org/job/",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_quota() -> GPUQuota:
    """Create sample GPU quota."""
    return GPUQuota(
        organization_id="org-test-123",
        max_concurrent_jobs=4,
        max_gpu_hours_monthly=100,
        max_job_runtime_hours=8,
        current_concurrent_jobs=0,
        current_month_gpu_hours=0.0,
    )


@pytest.fixture
def mock_k8s_client():
    """Create mock Kubernetes client."""
    mock_client = MagicMock()
    mock_client.create_job.return_value = "gpu-job-12345678"
    mock_client.delete_job.return_value = True
    mock_client.get_job_status.return_value = {
        "job_name": "gpu-job-12345678",
        "active": 1,
        "succeeded": 0,
        "failed": 0,
        "gpu_status": "running",
    }
    return mock_client


# =============================================================================
# Phase 5: Template and Schedule Fixtures
# =============================================================================


@pytest.fixture
def sample_template_request(
    sample_embedding_config: EmbeddingJobConfig,
) -> TemplateCreateRequest:
    """Create sample template creation request."""
    return TemplateCreateRequest(
        name="My Embedding Template",
        description="Standard embedding generation for code repos",
        job_type=GPUJobType.EMBEDDING_GENERATION,
        config=sample_embedding_config,
        priority=GPUJobPriority.NORMAL,
        gpu_memory_gb=8,
        gpu_count=1,
        max_runtime_hours=2,
        checkpoint_enabled=True,
        is_public=False,
        tags=["embedding", "codebert"],
    )


@pytest.fixture
def sample_template(sample_embedding_config: EmbeddingJobConfig) -> GPUJobTemplate:
    """Create sample GPU job template."""
    return GPUJobTemplate(
        template_id="tpl-12345678",
        organization_id="org-test-123",
        user_id="user-test-456",
        name="My Embedding Template",
        description="Standard embedding generation",
        job_type=GPUJobType.EMBEDDING_GENERATION,
        config=sample_embedding_config,
        priority=GPUJobPriority.NORMAL,
        gpu_memory_gb=8,
        gpu_count=1,
        max_runtime_hours=2,
        checkpoint_enabled=True,
        is_public=False,
        tags=["embedding"],
        use_count=0,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_schedule_request(
    sample_embedding_config: EmbeddingJobConfig,
) -> ScheduleCreateRequest:
    """Create sample schedule creation request with inline config."""
    return ScheduleCreateRequest(
        name="Daily Embedding Update",
        description="Updates embeddings every day at 2 AM",
        job_type=GPUJobType.EMBEDDING_GENERATION,
        config=sample_embedding_config,
        priority=GPUJobPriority.LOW,
        gpu_memory_gb=8,
        gpu_count=1,
        max_runtime_hours=4,
        checkpoint_enabled=True,
        frequency=ScheduleFrequency.DAILY,
        timezone="UTC",
    )


@pytest.fixture
def sample_schedule(sample_embedding_config: EmbeddingJobConfig) -> GPUScheduledJob:
    """Create sample GPU scheduled job."""
    now = datetime.now(timezone.utc)
    return GPUScheduledJob(
        schedule_id="sch-12345678",
        organization_id="org-test-123",
        user_id="user-test-456",
        name="Daily Embedding Update",
        description="Updates embeddings every day at 2 AM",
        job_type=GPUJobType.EMBEDDING_GENERATION,
        config=sample_embedding_config,
        priority=GPUJobPriority.LOW,
        gpu_memory_gb=8,
        gpu_count=1,
        max_runtime_hours=4,
        checkpoint_enabled=True,
        frequency=ScheduleFrequency.DAILY,
        timezone="UTC",
        status=ScheduledJobStatus.ACTIVE,
        next_run_at=now,
        run_count=0,
        failure_count=0,
        consecutive_failures=0,
        created_at=now,
    )


@pytest.fixture
def job_template_service(mock_dynamodb: dict[str, Any]):
    """Create job template service with mocked DynamoDB."""
    from src.services.gpu_scheduler.job_template_service import GPUJobTemplateService

    service = GPUJobTemplateService(
        table_name=f"aura-gpu-templates-{TEST_ENV}",
        region=AWS_REGION,
    )
    # Override table to use mocked table
    service._table = mock_dynamodb["templates_table"]
    return service


@pytest.fixture
def scheduled_job_service(mock_dynamodb: dict[str, Any]):
    """Create scheduled job service with mocked DynamoDB."""
    from src.services.gpu_scheduler.scheduled_job_service import GPUScheduledJobService

    service = GPUScheduledJobService(
        schedules_table_name=f"aura-gpu-schedules-{TEST_ENV}",
        templates_table_name=f"aura-gpu-templates-{TEST_ENV}",
        region=AWS_REGION,
    )
    # Override table to use mocked table
    service._schedules_table = mock_dynamodb["schedules_table"]
    return service


@pytest.fixture
def stalled_job_detector(mock_dynamodb: dict[str, Any]):
    """Create stalled job detector with mocked DynamoDB."""
    from src.services.gpu_scheduler.stalled_job_detector import StalledJobDetector

    return StalledJobDetector(
        jobs_table=mock_dynamodb["jobs_table"],
        sns_client=None,
        alert_topic_arn=None,
    )
