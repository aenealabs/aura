"""Shared fixtures for Runbook Agent tests."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.services.runbook.incident_detector import (
    ErrorSignature,
    Incident,
    IncidentType,
    ResolutionStep,
)


@pytest.fixture
def mock_boto3_clients():
    """Mock all boto3 clients used by runbook services."""
    with patch("boto3.client") as mock_client:
        # Create mock clients for each service
        mock_logs = MagicMock()
        mock_cf = MagicMock()
        mock_codebuild = MagicMock()
        mock_dynamodb = MagicMock()
        mock_bedrock = MagicMock()
        mock_events = MagicMock()

        def get_client(service, **kwargs):
            clients = {
                "logs": mock_logs,
                "cloudformation": mock_cf,
                "codebuild": mock_codebuild,
                "dynamodb": mock_dynamodb,
                "bedrock-runtime": mock_bedrock,
                "events": mock_events,
            }
            return clients.get(service, MagicMock())

        mock_client.side_effect = get_client

        yield {
            "logs": mock_logs,
            "cloudformation": mock_cf,
            "codebuild": mock_codebuild,
            "dynamodb": mock_dynamodb,
            "bedrock": mock_bedrock,
            "events": mock_events,
        }


@pytest.fixture
def docker_incident():
    """Create a Docker platform mismatch incident."""
    return Incident(
        id="cb-docker-001",
        incident_type=IncidentType.DOCKER_BUILD_FIX,
        title="Docker Platform Mismatch",
        description="Docker image built on ARM64 fails on AMD64 EKS nodes",
        error_messages=[
            "exec format error",
            "exit code: 255",
            "standard_init_linux.go:228: exec user process caused: exec format error",
        ],
        error_signatures=[
            ErrorSignature(
                pattern=r"exec format error",
                service="docker",
                severity="high",
                keywords=["docker", "platform", "architecture", "arm64", "amd64"],
            ),
        ],
        resolution_steps=[
            ResolutionStep(
                command="docker build --platform linux/amd64 -t image:tag .",
                output="Build successful",
                timestamp=datetime.now(),
                success=True,
                description="Build with explicit platform flag",
            ),
        ],
        affected_services=["docker", "ecr", "eks"],
        affected_resources=["aura-api-dev", "codebuild-project"],
        root_cause="Docker image architecture mismatch (ARM64 vs AMD64)",
        start_time=datetime(2024, 1, 1, 10, 0, 0),
        end_time=datetime(2024, 1, 1, 10, 30, 0),
        source="codebuild",
        source_id="aura-application-deploy-dev:build-123",
        confidence=0.92,
        metadata={
            "failed_build_id": "build-fail-123",
            "success_build_id": "build-success-456",
        },
    )


@pytest.fixture
def iam_incident():
    """Create an IAM permission fix incident."""
    return Incident(
        id="cb-iam-001",
        incident_type=IncidentType.IAM_PERMISSION_FIX,
        title="Bedrock Guardrails AccessDenied",
        description="CodeBuild failed due to missing bedrock:ListTagsForResource permission",
        error_messages=[
            "An error occurred (AccessDenied) when calling the ListTagsForResource operation",
            "User: arn:aws:sts::123456789012:assumed-role/codebuild-role is not authorized",
        ],
        error_signatures=[
            ErrorSignature(
                pattern=r"AccessDenied.*ListTagsForResource",
                service="bedrock",
                severity="high",
                keywords=["bedrock", "iam", "permissions", "guardrails"],
            ),
        ],
        resolution_steps=[
            ResolutionStep(
                command="aws cloudformation update-stack --stack-name codebuild-iam ...",
                output="Stack update initiated",
                timestamp=datetime.now(),
                success=True,
                description="Add bedrock:ListTagsForResource to IAM policy",
            ),
        ],
        affected_services=["bedrock", "iam", "cloudformation"],
        affected_resources=[
            "codebuild-application.yaml",
            "aura-bedrock-guardrails-dev",
        ],
        root_cause="Missing bedrock:ListTagsForResource IAM permission",
        start_time=datetime(2024, 1, 2, 14, 0, 0),
        end_time=datetime(2024, 1, 2, 15, 30, 0),
        source="codebuild",
        source_id="aura-application-deploy-dev:build-456",
        confidence=0.95,
    )


@pytest.fixture
def shell_syntax_incident():
    """Create a shell syntax fix incident."""
    return Incident(
        id="cb-shell-001",
        incident_type=IncidentType.SHELL_SYNTAX_FIX,
        title="CodeBuild Shell Syntax Error",
        description="Buildspec used bash-specific [[ ]] syntax but CodeBuild defaulted to /bin/sh",
        error_messages=[
            "/codebuild/output/tmp/script.sh: 12: [[: not found",
            "exit code: 127",
        ],
        error_signatures=[
            ErrorSignature(
                pattern=r"\[\[:\s*not found",
                service="codebuild",
                severity="medium",
                keywords=["bash", "shell", "syntax", "buildspec", "conditional"],
            ),
        ],
        resolution_steps=[
            ResolutionStep(
                command="# Add to buildspec.yml env section: shell: bash",
                output="Buildspec updated",
                timestamp=datetime.now(),
                success=True,
                description="Add shell: bash to buildspec env section",
            ),
        ],
        affected_services=["codebuild"],
        affected_resources=["buildspec-application.yml"],
        root_cause="Bash-specific syntax ([[ ]]) in POSIX shell environment",
        start_time=datetime(2024, 1, 3, 9, 0, 0),
        end_time=datetime(2024, 1, 3, 9, 15, 0),
        source="codebuild",
        source_id="aura-application-deploy-dev:build-789",
        confidence=0.88,
    )


@pytest.fixture
def ecr_conflict_incident():
    """Create an ECR repository conflict incident."""
    return Incident(
        id="cf-ecr-001",
        incident_type=IncidentType.ECR_CONFLICT_RESOLUTION,
        title="ECR Repository Already Exists",
        description="CloudFormation failed because ECR repository was created outside of stack",
        error_messages=[
            'Resource handler returned message: "Repository already exists"',
            "AlreadyExistsException",
        ],
        error_signatures=[
            ErrorSignature(
                pattern=r"AlreadyExists.*repository",
                service="ecr",
                severity="medium",
                keywords=["ecr", "repository", "exists", "conflict", "cloudformation"],
            ),
        ],
        resolution_steps=[
            ResolutionStep(
                command="aws cloudformation delete-stack --stack-name aura-ecr-api-dev",
                output="Stack deletion initiated",
                timestamp=datetime.now(),
                success=True,
                description="Delete failed CloudFormation stack",
            ),
        ],
        affected_services=["ecr", "cloudformation"],
        affected_resources=["aura-ecr-api-dev", "aura-api-dev"],
        root_cause="ECR repository exists outside CloudFormation management",
        start_time=datetime(2024, 1, 4, 11, 0, 0),
        end_time=datetime(2024, 1, 4, 11, 20, 0),
        source="cloudformation",
        source_id="aura-ecr-api-dev",
        confidence=0.82,
    )


@pytest.fixture
def cloudformation_rollback_incident():
    """Create a CloudFormation rollback recovery incident."""
    return Incident(
        id="cf-rollback-001",
        incident_type=IncidentType.CLOUDFORMATION_ROLLBACK_RECOVERY,
        title="CloudFormation Stack Rollback Recovery",
        description="Stack entered ROLLBACK_COMPLETE state and was recovered",
        error_messages=[
            "Stack aura-api-dev is in ROLLBACK_COMPLETE state",
            "Resource creation failed",
        ],
        error_signatures=[
            ErrorSignature(
                pattern=r"ROLLBACK_COMPLETE",
                service="cloudformation",
                severity="high",
                keywords=["cloudformation", "rollback", "stack", "failed"],
            ),
        ],
        resolution_steps=[
            ResolutionStep(
                command="aws cloudformation delete-stack --stack-name aura-api-dev",
                output="Stack deletion initiated",
                timestamp=datetime.now(),
                success=True,
                description="Delete failed stack",
            ),
            ResolutionStep(
                command="aws codebuild start-build --project-name aura-application-deploy-dev",
                output="Build started",
                timestamp=datetime.now(),
                success=True,
                description="Re-deploy via CodeBuild",
            ),
        ],
        affected_services=["cloudformation", "codebuild"],
        affected_resources=["aura-api-dev"],
        root_cause="Stack creation failed and required cleanup",
        start_time=datetime(2024, 1, 5, 16, 0, 0),
        end_time=datetime(2024, 1, 5, 16, 45, 0),
        source="cloudformation",
        source_id="aura-api-dev",
        confidence=0.78,
    )


@pytest.fixture
def sample_runbook_content():
    """Sample runbook content for testing."""
    return """# Runbook: Docker Platform Mismatch

**Purpose:** Resolve Docker image architecture mismatch errors in CI/CD pipelines

**Audience:** DevOps Engineers, Platform Team

**Estimated Time:** 15-30 minutes

**Last Updated:** Dec 11, 2024

---

## Problem Description

Docker images built on ARM64 architecture fail when deployed to AMD64 EKS nodes.

**Affected Services:** docker, ecr, eks

### Symptoms

```
exec format error
standard_init_linux.go:228: exec user process caused: exec format error
exit code: 255
```

### Root Cause

Docker image architecture mismatch - images built on ARM64 (Apple Silicon, Graviton)
cannot run on AMD64 (x86_64) nodes.

---

## Quick Resolution

### Step 1: Rebuild with Platform Flag

```bash
docker build --platform linux/amd64 -t image:tag .
```

---

## Prevention

- Always specify `--platform linux/amd64` in Docker build commands
- Add architecture verification to buildspecs
- Use multi-platform base images where possible

---

## Related Documentation

- [Docker Platform Documentation](https://docs.docker.com/build/building/multi-platform/)
- [CLAUDE.md - Docker Builds](../../CLAUDE.md#docker-builds-important---architecture)
"""
