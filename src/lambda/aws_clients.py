"""
Centralized AWS client factory for Lambda functions.

This module provides lazy-initialized, cached AWS clients for Lambda functions.
Using functools.lru_cache ensures:
- Clients are only created when first used (lazy initialization)
- Clients are reused across Lambda warm invocations (caching)
- Tests can reset client state via clear_all_caches()

Usage:
    from src.lambda.aws_clients import get_s3_client, get_dynamodb_resource

    def handler(event, context):
        s3 = get_s3_client()
        s3.put_object(...)

References:
- GitHub Issue #466: Refactor Lambda modules to use lazy boto3 client initialization
- Kelly (Test Architect) analysis: Module-level boto3 client creation causes test pollution
- Architecture team recommendation: Use functools.lru_cache pattern
"""

import functools
import os
from typing import Optional

import boto3


# =============================================================================
# S3 Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_s3_client():
    """Get or create S3 client (cached for Lambda warm starts)."""
    return boto3.client("s3")


# =============================================================================
# SNS Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_sns_client():
    """Get or create SNS client (cached for Lambda warm starts)."""
    return boto3.client("sns")


# =============================================================================
# EKS Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_eks_client():
    """Get or create EKS client (cached for Lambda warm starts)."""
    return boto3.client("eks")


# =============================================================================
# DynamoDB Resource and Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_dynamodb_resource(region_name: Optional[str] = None):
    """Get or create DynamoDB resource (cached for Lambda warm starts)."""
    if region_name:
        return boto3.resource("dynamodb", region_name=region_name)
    return boto3.resource("dynamodb")


@functools.lru_cache(maxsize=1)
def get_dynamodb_client():
    """Get or create DynamoDB client (cached for Lambda warm starts)."""
    return boto3.client("dynamodb")


# =============================================================================
# Lambda Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_lambda_client():
    """Get or create Lambda client (cached for Lambda warm starts)."""
    return boto3.client("lambda")


# =============================================================================
# CloudWatch Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_cloudwatch_client():
    """Get or create CloudWatch client (cached for Lambda warm starts)."""
    return boto3.client("cloudwatch")


# =============================================================================
# Step Functions Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_stepfunctions_client():
    """Get or create Step Functions client (cached for Lambda warm starts)."""
    return boto3.client("stepfunctions")


# =============================================================================
# Service Catalog Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_servicecatalog_client():
    """Get or create Service Catalog client (cached for Lambda warm starts)."""
    return boto3.client("servicecatalog")


# =============================================================================
# STS Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_sts_client():
    """Get or create STS client (cached for Lambda warm starts)."""
    return boto3.client("sts")


# =============================================================================
# CloudWatch Logs Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_logs_client():
    """Get or create CloudWatch Logs client (cached for Lambda warm starts)."""
    return boto3.client("logs")


# =============================================================================
# SQS Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_sqs_client():
    """Get or create SQS client (cached for Lambda warm starts)."""
    return boto3.client("sqs")


# =============================================================================
# Bedrock Runtime Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_bedrock_runtime_client():
    """Get or create Bedrock Runtime client (cached for Lambda warm starts)."""
    return boto3.client("bedrock-runtime")


# =============================================================================
# EventBridge Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_events_client(region_name: Optional[str] = None):
    """Get or create EventBridge client (cached for Lambda warm starts)."""
    if region_name:
        return boto3.client("events", region_name=region_name)
    return boto3.client("events")


# =============================================================================
# SSM Client
# =============================================================================
@functools.lru_cache(maxsize=1)
def get_ssm_client(region_name: Optional[str] = None):
    """Get or create SSM client (cached for Lambda warm starts)."""
    if region_name:
        return boto3.client("ssm", region_name=region_name)
    return boto3.client("ssm")


# =============================================================================
# API Gateway Management API Client (uncached - requires dynamic endpoint)
# =============================================================================
def get_apigateway_management_client(endpoint_url: str):
    """
    Get API Gateway Management API client.

    Note: This is NOT cached because the endpoint_url varies per request.
    Each WebSocket connection may have a different endpoint.
    """
    return boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)


# =============================================================================
# Cache Management (for testing)
# =============================================================================
def clear_all_caches():
    """
    Clear all client caches.

    Call this in test fixtures to ensure test isolation.
    Each test should get fresh clients with the test's environment variables.

    Usage in conftest.py:
        @pytest.fixture(autouse=True)
        def reset_aws_clients():
            from src.lambda.aws_clients import clear_all_caches
            clear_all_caches()
            yield
            clear_all_caches()
    """
    get_s3_client.cache_clear()
    get_sns_client.cache_clear()
    get_eks_client.cache_clear()
    get_dynamodb_resource.cache_clear()
    get_dynamodb_client.cache_clear()
    get_lambda_client.cache_clear()
    get_cloudwatch_client.cache_clear()
    get_stepfunctions_client.cache_clear()
    get_servicecatalog_client.cache_clear()
    get_sts_client.cache_clear()
    get_logs_client.cache_clear()
    get_sqs_client.cache_clear()
    get_bedrock_runtime_client.cache_clear()
    get_events_client.cache_clear()
    get_ssm_client.cache_clear()


# =============================================================================
# Convenience: Get region from environment
# =============================================================================
def get_aws_region() -> str:
    """Get AWS region from environment, with sensible default."""
    return os.environ.get(
        "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    )
