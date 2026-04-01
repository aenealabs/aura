#!/usr/bin/env python3
"""
DEV Environment Kill-Switch for Project Aura
=============================================
Safely shuts down or restores the DEV environment to save significant monthly
on always-on AWS resources (Neptune, OpenSearch, EKS, VPC Endpoints, etc.).

Modeled on scripts/qa_killswitch.py. Handles ~80 stacks (vs 9 in QA).
Core infrastructure (9 stacks) restores directly via CloudFormation;
upper layers restore via CodeBuild triggers (single source of truth).

Usage:
    python scripts/dev_killswitch.py shutdown              # Dry-run (default)
    python scripts/dev_killswitch.py shutdown --execute     # Actually delete stacks
    python scripts/dev_killswitch.py restore                # Dry-run restore plan
    python scripts/dev_killswitch.py restore --execute      # Actually redeploy stacks
    python scripts/dev_killswitch.py status                 # Show current DEV state
    python scripts/dev_killswitch.py cleanup                # Dry-run: show orphaned costs
    python scripts/dev_killswitch.py cleanup --execute      # Clean up residual costs

Flags:
    --execute           Perform real operations (default is dry-run)
    --force             Skip interactive confirmation prompt
    --skip-snapshot     Skip Neptune snapshot during shutdown
    --verbose           Debug-level logging
    --region REGION     AWS region (default: us-east-1)

Exit codes:
    0 - Success
    1 - Pre-flight check failed or operation error
    2 - Fatal error (credentials, account mismatch)

Security:
    - Hardcoded to DEV environment only (no override)
    - Validates AWS account ID before any destructive action
    - Dry-run by default; requires --execute for real operations
    - Interactive confirmation (type 'DESTROY DEV') unless --force
    - All stack names validated against PROTECTED_STACKS before deletion
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_ENVIRONMENTS = frozenset(["dev"])
PROJECT_NAME = "aura"
ENVIRONMENT = "dev"
DEFAULT_REGION = "us-east-1"

# ---------------------------------------------------------------------------
# Stack Definitions (shutdown order)
# ---------------------------------------------------------------------------
# Stacks managed by the kill-switch, organized by shutdown phase.
# Phase numbers determine deletion order; stacks in the same phase
# can be deleted in parallel (no inter-dependencies within a phase).

STACK_DEFINITIONS = [
    # -----------------------------------------------------------------------
    # Phase 2: Layer 9 - Scanning Engine (8 stacks, ordered by dependency)
    # Cross-stack exports require sequential deletion:
    #   delete_order 1: monitoring, eventbridge, cleanup, ecr (leaf stacks)
    #   delete_order 2: workflow (after monitoring deleted)
    #   delete_order 3: iam, networking (after workflow deleted)
    #   delete_order 4: infra (after iam and cleanup deleted)
    # -----------------------------------------------------------------------
    {
        "name": f"{PROJECT_NAME}-vuln-scan-monitoring-{ENVIRONMENT}",
        "phase": 2,
        "template": "deploy/cloudformation/vuln-scan-monitoring.yaml",
        "layer": "scanning",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-vuln-scan-eventbridge-{ENVIRONMENT}",
        "phase": 2,
        "template": "deploy/cloudformation/vuln-scan-eventbridge.yaml",
        "layer": "scanning",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-vuln-scan-cleanup-{ENVIRONMENT}",
        "phase": 2,
        "template": "deploy/cloudformation/vuln-scan-cleanup.yaml",
        "layer": "scanning",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-vuln-scan-ecr-{ENVIRONMENT}",
        "phase": 2,
        "template": "deploy/cloudformation/vuln-scan-ecr.yaml",
        "layer": "scanning",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-vuln-scan-workflow-{ENVIRONMENT}",
        "phase": 2,
        "template": "deploy/cloudformation/vuln-scan-workflow.yaml",
        "layer": "scanning",
        "delete_order": 2,
    },
    {
        "name": f"{PROJECT_NAME}-vuln-scan-networking-{ENVIRONMENT}",
        "phase": 2,
        "template": "deploy/cloudformation/vuln-scan-networking.yaml",
        "layer": "scanning",
        "delete_order": 3,
    },
    {
        "name": f"{PROJECT_NAME}-vuln-scan-iam-{ENVIRONMENT}",
        "phase": 2,
        "template": "deploy/cloudformation/vuln-scan-iam.yaml",
        "layer": "scanning",
        "delete_order": 3,
    },
    {
        "name": f"{PROJECT_NAME}-vuln-scan-infra-{ENVIRONMENT}",
        "phase": 2,
        "template": "deploy/cloudformation/vuln-scan-infra.yaml",
        "layer": "scanning",
        "delete_order": 4,
    },
    # -----------------------------------------------------------------------
    # Phase 3: Layer 8 - Security Services (13 stacks, parallel)
    # -----------------------------------------------------------------------
    {
        "name": f"{PROJECT_NAME}-runtime-security-correlation-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/runtime-security-correlation.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-runtime-security-baselines-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/runtime-security-baselines.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-runtime-security-discovery-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/runtime-security-discovery.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-runtime-security-interceptor-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/runtime-security-interceptor.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-capability-governance-monitoring-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/capability-governance-monitoring.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-capability-governance-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/capability-governance.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-semantic-guardrails-monitoring-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/semantic-guardrails-monitoring.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-semantic-guardrails-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/semantic-guardrails.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-red-team-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/red-team.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-drift-detection-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/drift-detection.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-guardduty-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/guardduty.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-config-compliance-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/config-compliance.yaml",
        "layer": "security",
    },
    {
        "name": f"{PROJECT_NAME}-iam-security-alerting-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/iam-security-alerting.yaml",
        "layer": "security",
    },
    # -----------------------------------------------------------------------
    # Phase 4: Layer 7 - Sandbox / Test Environments (13 stacks, ordered)
    # Cross-stack exports require sequential deletion:
    #   delete_order 1: test-env-*, ssr-training*, hitl-workflow (leaf stacks)
    #   delete_order 2: sandbox (after hitl-workflow deleted)
    # -----------------------------------------------------------------------
    {
        "name": f"{PROJECT_NAME}-test-env-scheduler-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/test-env-scheduler.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-test-env-budgets-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/test-env-budgets.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-test-env-monitoring-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/test-env-monitoring.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-test-env-marketplace-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/test-env-marketplace.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-test-env-namespace-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/test-env-namespace.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-test-env-approval-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/test-env-approval.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-test-env-catalog-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/test-env-catalog.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-test-env-iam-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/test-env-iam.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-test-env-state-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/test-env-state.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-hitl-workflow-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/hitl-workflow.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-ssr-training-pipeline-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/ssr-training-pipeline.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-ssr-training-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/ssr-training.yaml",
        "layer": "sandbox",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-sandbox-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/sandbox.yaml",
        "layer": "sandbox",
        "delete_order": 2,
    },
    # -----------------------------------------------------------------------
    # Phase 5: Layer 6 - Serverless (18 stacks, ordered by dependency)
    # Cross-stack exports require sequential deletion:
    #   delete_order 1: incident-investigation, all other leaf stacks
    #   delete_order 2: incident-response (after incident-investigation)
    # -----------------------------------------------------------------------
    {
        "name": f"{PROJECT_NAME}-constitutional-ai-evaluation-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/constitutional-ai-evaluation.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-constitutional-audit-queue-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/constitutional-audit-queue.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-gpu-scheduler-infra-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/gpu-scheduler-infra.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-env-drift-lambda-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/env-drift-lambda.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-deployment-pipeline-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/deployment-pipeline.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-scheduling-infrastructure-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/scheduling-infrastructure.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-checkpoint-websocket-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/checkpoint-websocket.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-runbook-agent-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/runbook-agent.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-dns-blocklist-lambda-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/dns-blocklist-lambda.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-orchestrator-dispatcher-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/orchestrator-dispatcher.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-agent-queues-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/agent-queues.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-a2a-infrastructure-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/a2a-infrastructure.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-hitl-callback-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/hitl-callback.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-hitl-scheduler-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/hitl-scheduler.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-threat-intel-scheduler-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/threat-intel-scheduler.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-incident-investigation-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/incident-investigation-workflow.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    {
        "name": f"{PROJECT_NAME}-incident-response-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/incident-response.yaml",
        "layer": "serverless",
        "delete_order": 2,
    },
    {
        "name": f"{PROJECT_NAME}-chat-assistant-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/chat-assistant.yaml",
        "layer": "serverless",
        "delete_order": 1,
    },
    # -----------------------------------------------------------------------
    # Phase 6: Layer 5 - Observability (8 stacks, parallel)
    # (Keeping: secrets, disaster-recovery, log-retention-sync,
    #  compliance-settings-sync)
    # -----------------------------------------------------------------------
    {
        "name": f"{PROJECT_NAME}-dev-cost-scheduler-{ENVIRONMENT}",
        "phase": 6,
        "template": "deploy/cloudformation/dev-cost-scheduler.yaml",
        "layer": "observability",
    },
    {
        "name": f"{PROJECT_NAME}-gpu-monitoring-{ENVIRONMENT}",
        "phase": 6,
        "template": "deploy/cloudformation/gpu-monitoring.yaml",
        "layer": "observability",
    },
    {
        "name": f"{PROJECT_NAME}-alignment-alerts-{ENVIRONMENT}",
        "phase": 6,
        "template": "deploy/cloudformation/alignment-alerts.yaml",
        "layer": "observability",
    },
    {
        "name": f"{PROJECT_NAME}-otel-collector-{ENVIRONMENT}",
        "phase": 6,
        "template": "deploy/cloudformation/otel-collector.yaml",
        "layer": "observability",
    },
    {
        "name": f"{PROJECT_NAME}-realtime-monitoring-{ENVIRONMENT}",
        "phase": 6,
        "template": "deploy/cloudformation/realtime-monitoring.yaml",
        "layer": "observability",
    },
    {
        "name": f"{PROJECT_NAME}-org-cost-monitoring-{ENVIRONMENT}",
        "phase": 6,
        "template": "deploy/cloudformation/org-cost-monitoring.yaml",
        "layer": "observability",
    },
    {
        "name": f"{PROJECT_NAME}-cost-alerts-{ENVIRONMENT}",
        "phase": 6,
        "template": "deploy/cloudformation/aura-cost-alerts.yaml",
        "layer": "observability",
    },
    {
        "name": f"{PROJECT_NAME}-monitoring-{ENVIRONMENT}",
        "phase": 6,
        "template": "deploy/cloudformation/monitoring.yaml",
        "layer": "observability",
    },
    # -----------------------------------------------------------------------
    # Phase 7: Layer 4 - Application Services (10 stacks, parallel)
    # (Keeping: cognito, marketplace, diagram-service-*, idp-infrastructure,
    #  customer-onboarding)
    # -----------------------------------------------------------------------
    {
        "name": f"{PROJECT_NAME}-irsa-api-{ENVIRONMENT}",
        "phase": 7,
        "template": "deploy/cloudformation/irsa-api.yaml",
        "layer": "application",
    },
    {
        "name": f"{PROJECT_NAME}-irsa-memory-service-{ENVIRONMENT}",
        "phase": 7,
        "template": "deploy/cloudformation/irsa-memory-service.yaml",
        "layer": "application",
    },
    {
        "name": f"{PROJECT_NAME}-gpu-scheduler-irsa-{ENVIRONMENT}",
        "phase": 7,
        "template": "deploy/cloudformation/gpu-scheduler-irsa.yaml",
        "layer": "application",
    },
    {
        "name": f"{PROJECT_NAME}-env-validator-irsa-{ENVIRONMENT}",
        "phase": 7,
        "template": "deploy/cloudformation/env-validator-irsa.yaml",
        "layer": "application",
    },
    {
        "name": f"{PROJECT_NAME}-cluster-autoscaler-irsa-{ENVIRONMENT}",
        "phase": 7,
        "template": "deploy/cloudformation/cluster-autoscaler-irsa.yaml",
        "layer": "application",
    },
    {
        "name": f"{PROJECT_NAME}-bedrock-infrastructure-{ENVIRONMENT}",
        "phase": 7,
        "template": "deploy/cloudformation/aura-bedrock-infrastructure.yaml",
        "layer": "application",
    },
    {
        "name": f"{PROJECT_NAME}-bedrock-guardrails-{ENVIRONMENT}",
        "phase": 7,
        "template": "deploy/cloudformation/bedrock-guardrails.yaml",
        "layer": "application",
    },
    {
        "name": f"{PROJECT_NAME}-marketing-{ENVIRONMENT}",
        "phase": 7,
        "template": "deploy/cloudformation/marketing.yaml",
        "layer": "application",
    },
    {
        "name": f"{PROJECT_NAME}-docs-portal-{ENVIRONMENT}",
        "phase": 7,
        "template": "deploy/cloudformation/docs-portal.yaml",
        "layer": "application",
    },
    {
        "name": f"{PROJECT_NAME}-alb-controller-{ENVIRONMENT}",
        "phase": 7,
        "template": "deploy/cloudformation/alb-controller.yaml",
        "layer": "application",
    },
    # -----------------------------------------------------------------------
    # Phase 8: Network Services (1 stack - dnsmasq ECS Fargate)
    # -----------------------------------------------------------------------
    {
        "name": f"{PROJECT_NAME}-network-services-{ENVIRONMENT}",
        "phase": 8,
        "template": "deploy/cloudformation/network-services.yaml",
        "layer": "network",
    },
    # -----------------------------------------------------------------------
    # Phase 9: Compute - Node Groups (4 stacks, parallel)
    # -----------------------------------------------------------------------
    {
        "name": f"{PROJECT_NAME}-nodegroup-general-{ENVIRONMENT}",
        "phase": 9,
        "template": "deploy/cloudformation/eks-nodegroup-general.yaml",
        "layer": "compute",
    },
    {
        "name": f"{PROJECT_NAME}-nodegroup-memory-{ENVIRONMENT}",
        "phase": 9,
        "template": "deploy/cloudformation/eks-nodegroup-memory.yaml",
        "layer": "compute",
    },
    {
        "name": f"{PROJECT_NAME}-nodegroup-gpu-{ENVIRONMENT}",
        "phase": 9,
        "template": "deploy/cloudformation/eks-nodegroup-gpu.yaml",
        "layer": "compute",
    },
    {
        "name": f"{PROJECT_NAME}-neural-memory-gpu-{ENVIRONMENT}",
        "phase": 9,
        "template": "deploy/cloudformation/neural-memory-gpu.yaml",
        "layer": "compute",
    },
    # -----------------------------------------------------------------------
    # Phase 10: Compute - EKS Control Plane (1 stack)
    # -----------------------------------------------------------------------
    {
        "name": f"{PROJECT_NAME}-eks-{ENVIRONMENT}",
        "phase": 10,
        "template": "deploy/cloudformation/eks.yaml",
        "layer": "compute",
    },
    # -----------------------------------------------------------------------
    # Phase 11: Data Stores (3 stacks, parallel)
    # -----------------------------------------------------------------------
    {
        "name": f"{PROJECT_NAME}-neptune-{ENVIRONMENT}",
        "phase": 11,
        "template": "deploy/cloudformation/neptune-simplified.yaml",
        "layer": "data",
    },
    {
        "name": f"{PROJECT_NAME}-opensearch-{ENVIRONMENT}",
        "phase": 11,
        "template": "deploy/cloudformation/opensearch.yaml",
        "layer": "data",
    },
    {
        "name": f"{PROJECT_NAME}-elasticache-{ENVIRONMENT}",
        "phase": 11,
        "template": "deploy/cloudformation/elasticache.yaml",
        "layer": "data",
    },
    # -----------------------------------------------------------------------
    # Phase 12: Foundation - VPC Endpoints (1 stack, last to delete)
    # -----------------------------------------------------------------------
    {
        "name": f"{PROJECT_NAME}-vpc-endpoints-{ENVIRONMENT}",
        "phase": 12,
        "template": "deploy/cloudformation/vpc-endpoints.yaml",
        "layer": "foundation",
    },
]

# Stacks that must NEVER be deleted (safety allowlist)
PROTECTED_STACKS = frozenset(
    [
        # Foundation (networking backbone)
        f"{PROJECT_NAME}-vpc-{ENVIRONMENT}",
        f"{PROJECT_NAME}-networking-{ENVIRONMENT}",
        f"{PROJECT_NAME}-security-{ENVIRONMENT}",
        f"{PROJECT_NAME}-iam-{ENVIRONMENT}",
        f"{PROJECT_NAME}-kms-{ENVIRONMENT}",
        f"{PROJECT_NAME}-route53-dns-{ENVIRONMENT}",
        f"{PROJECT_NAME}-build-cache-{ENVIRONMENT}",
        f"{PROJECT_NAME}-ecr-base-images-{ENVIRONMENT}",
        # Data (state management - DynamoDB on-demand, minimal cost)
        f"{PROJECT_NAME}-s3-{ENVIRONMENT}",
        f"{PROJECT_NAME}-dynamodb-{ENVIRONMENT}",
        f"{PROJECT_NAME}-repository-tables-{ENVIRONMENT}",
        f"{PROJECT_NAME}-cloud-discovery-{ENVIRONMENT}",
        f"{PROJECT_NAME}-dashboard-dynamodb-{ENVIRONMENT}",
        f"{PROJECT_NAME}-context-provenance-{ENVIRONMENT}",
        f"{PROJECT_NAME}-supply-chain-dynamodb-{ENVIRONMENT}",
        f"{PROJECT_NAME}-runtime-security-dynamodb-{ENVIRONMENT}",
        f"{PROJECT_NAME}-ai-security-dynamodb-{ENVIRONMENT}",
        f"{PROJECT_NAME}-memory-evolution-dynamodb-{ENVIRONMENT}",
        # Application (identity & config)
        f"{PROJECT_NAME}-cognito-{ENVIRONMENT}",
        f"{PROJECT_NAME}-marketplace-{ENVIRONMENT}",
        f"{PROJECT_NAME}-iam-diagram-service-{ENVIRONMENT}",
        f"{PROJECT_NAME}-diagram-service-ssm-{ENVIRONMENT}",
        f"{PROJECT_NAME}-idp-infrastructure-{ENVIRONMENT}",
        f"{PROJECT_NAME}-customer-onboarding-{ENVIRONMENT}",
        # Observability (minimal cost infrastructure)
        f"{PROJECT_NAME}-secrets-{ENVIRONMENT}",
        f"{PROJECT_NAME}-disaster-recovery-{ENVIRONMENT}",
        f"{PROJECT_NAME}-log-retention-sync-{ENVIRONMENT}",
        f"{PROJECT_NAME}-compliance-settings-sync-{ENVIRONMENT}",
        # Serverless (state storage)
        f"{PROJECT_NAME}-checkpoint-dynamodb-{ENVIRONMENT}",
        f"{PROJECT_NAME}-serverless-permission-boundary-{ENVIRONMENT}",
        # Bootstrap / Organization
        f"{PROJECT_NAME}-organizations",
        f"{PROJECT_NAME}-org-cloudtrail",
        f"{PROJECT_NAME}-route53-cross-account-role",
        f"{PROJECT_NAME}-account-bootstrap-{ENVIRONMENT}",
        f"{PROJECT_NAME}-account-migration-bootstrap-{ENVIRONMENT}",
        # ECR repos (container images, $0.10/ea)
        f"{PROJECT_NAME}-ecr-agent-orchestrator-{ENVIRONMENT}",
        f"{PROJECT_NAME}-ecr-api-{ENVIRONMENT}",
        f"{PROJECT_NAME}-ecr-memory-service-{ENVIRONMENT}",
        f"{PROJECT_NAME}-ecr-frontend-{ENVIRONMENT}",
        f"{PROJECT_NAME}-ecr-meta-orchestrator-{ENVIRONMENT}",
        f"{PROJECT_NAME}-ecr-runtime-incident-agent-{ENVIRONMENT}",
        f"{PROJECT_NAME}-ecr-dnsmasq-{ENVIRONMENT}",
        # ACM Certificate (free)
        f"{PROJECT_NAME}-acm-certificate-{ENVIRONMENT}",
    ]
)

# EventBridge schedules to disable during shutdown
EVENTBRIDGE_SCHEDULES = [
    f"{PROJECT_NAME}-dev-scale-down",
    f"{PROJECT_NAME}-dev-scale-up",
]

# CodeBuild projects to trigger during restore (upper layers)
CODEBUILD_RESTORE_PROJECTS = [
    f"{PROJECT_NAME}-application-deploy-{ENVIRONMENT}",
    f"{PROJECT_NAME}-observability-deploy-{ENVIRONMENT}",
    f"{PROJECT_NAME}-serverless-deploy-{ENVIRONMENT}",
    f"{PROJECT_NAME}-sandbox-deploy-{ENVIRONMENT}",
    f"{PROJECT_NAME}-security-deploy-{ENVIRONMENT}",
    f"{PROJECT_NAME}-vuln-scan-deploy-{ENVIRONMENT}",
]

SNS_TOPIC_NAME = f"{PROJECT_NAME}-operations-{ENVIRONMENT}"

# Foundation stacks that STAY running (parameters resolved from these)
FOUNDATION_STACKS = {
    "networking": f"{PROJECT_NAME}-networking-{ENVIRONMENT}",
    "security": f"{PROJECT_NAME}-security-{ENVIRONMENT}",
    "iam": f"{PROJECT_NAME}-iam-{ENVIRONMENT}",
}

STACK_DELETE_TIMEOUT = 1800  # 30 minutes
STACK_DELETE_POLL_INTERVAL = 15  # seconds
SNAPSHOT_TIMEOUT = 600  # 10 minutes

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
NC = "\033[0m"


def _setup_logging(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger("dev-killswitch")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return logger


log = _setup_logging()


def info(msg: str) -> None:
    log.info(f"{BLUE}[INFO]{NC} {msg}")


def success(msg: str) -> None:
    log.info(f"{GREEN}[OK]{NC} {msg}")


def warn(msg: str) -> None:
    log.warning(f"{YELLOW}[WARN]{NC} {msg}")


def error(msg: str) -> None:
    log.error(f"{RED}[ERROR]{NC} {msg}")


def phase_header(num: int, title: str) -> None:
    log.info(f"\n{BOLD}{CYAN}=== Phase {num}: {title} ==={NC}")


# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------


@dataclass
class DeletedStack:
    stack_name: str
    template_file: str
    deleted_at: str


@dataclass
class KillSwitchState:
    schema_version: int = 1
    environment: str = ENVIRONMENT
    status: str = "unknown"  # shutdown | running | partial
    shutdown_timestamp: Optional[str] = None
    shutdown_by: Optional[str] = None
    neptune_snapshot_id: Optional[str] = None
    deleted_stacks: List[Dict[str, str]] = field(default_factory=list)
    disabled_schedules: List[str] = field(default_factory=list)
    codebuild_restore_ids: List[str] = field(default_factory=list)
    restore_timestamp: Optional[str] = None
    restore_by: Optional[str] = None
    phases_completed: List[int] = field(default_factory=list)


def _state_local_path() -> Path:
    p = Path.home() / ".aura"
    p.mkdir(parents=True, exist_ok=True)
    return p / "dev-killswitch-state.json"


def _get_artifacts_bucket(cfn_client) -> Optional[str]:
    """Discover the S3 artifacts bucket from the s3 stack."""
    try:
        resp = cfn_client.describe_stacks(StackName=f"{PROJECT_NAME}-s3-{ENVIRONMENT}")
        for output in resp["Stacks"][0].get("Outputs", []):
            if output.get("OutputKey") == "ArtifactsBucketName":
                return output["OutputValue"]
    except ClientError:
        pass
    return None


def save_state(state: KillSwitchState, s3_client, cfn_client) -> None:
    data = json.dumps(asdict(state), indent=2, default=str)
    # Local
    local_path = _state_local_path()
    local_path.write_text(data)
    local_path.chmod(0o600)
    info(f"State saved locally: {local_path}")
    # S3
    bucket = _get_artifacts_bucket(cfn_client)
    if bucket:
        try:
            s3_client.put_object(
                Bucket=bucket,
                Key="killswitch/dev-state.json",
                Body=data,
                ContentType="application/json",
            )
            info(f"State saved to s3://{bucket}/killswitch/dev-state.json")
        except ClientError as e:
            warn(f"Could not save state to S3: {e}")


def load_state(s3_client, cfn_client) -> KillSwitchState:
    # Try S3 first
    bucket = _get_artifacts_bucket(cfn_client)
    if bucket:
        try:
            resp = s3_client.get_object(Bucket=bucket, Key="killswitch/dev-state.json")
            data = json.loads(resp["Body"].read().decode())
            info(f"State loaded from s3://{bucket}/killswitch/dev-state.json")
            return KillSwitchState(
                **{
                    k: v
                    for k, v in data.items()
                    if k in KillSwitchState.__dataclass_fields__
                }
            )
        except ClientError:
            pass
    # Fallback to local
    local_path = _state_local_path()
    if local_path.exists():
        data = json.loads(local_path.read_text())
        info(f"State loaded from {local_path}")
        return KillSwitchState(
            **{
                k: v
                for k, v in data.items()
                if k in KillSwitchState.__dataclass_fields__
            }
        )
    return KillSwitchState()


# ---------------------------------------------------------------------------
# Stack Manager
# ---------------------------------------------------------------------------


class StackManager:
    """Manages CloudFormation stack operations."""

    def __init__(self, cfn_client, region: str):
        self.cfn = cfn_client
        self.region = region

    def get_stack_status(self, stack_name: str) -> Optional[str]:
        try:
            resp = self.cfn.describe_stacks(StackName=stack_name)
            return resp["Stacks"][0]["StackStatus"]
        except ClientError as e:
            if "does not exist" in str(e):
                return None
            raise

    def get_stack_output(self, stack_name: str, output_key: str) -> Optional[str]:
        try:
            resp = self.cfn.describe_stacks(StackName=stack_name)
            for output in resp["Stacks"][0].get("Outputs", []):
                if output["OutputKey"] == output_key:
                    return output["OutputValue"]
        except ClientError:
            pass
        return None

    def delete_stack(self, stack_name: str, dry_run: bool = True) -> bool:
        # Safety: refuse to delete protected stacks
        if stack_name in PROTECTED_STACKS:
            error(f"BLOCKED: {stack_name} is in PROTECTED_STACKS")
            return False

        status = self.get_stack_status(stack_name)
        if status is None or status == "DELETE_COMPLETE":
            success(f"Stack {stack_name} already deleted (skipping)")
            return True

        if status.endswith("_IN_PROGRESS"):
            if "DELETE" in status:
                info(f"Stack {stack_name} deletion already in progress, " f"waiting...")
                return self._wait_for_delete(stack_name)
            else:
                error(f"Stack {stack_name} has active operation: {status}")
                return False

        if dry_run:
            info(f"[DRY-RUN] Would delete stack: {stack_name} " f"(current: {status})")
            return True

        info(f"Deleting stack: {stack_name} (current: {status})")
        try:
            self.cfn.delete_stack(StackName=stack_name)
            return self._wait_for_delete(stack_name)
        except ClientError as e:
            error(f"Failed to delete {stack_name}: {e}")
            return False

    def _wait_for_delete(self, stack_name: str) -> bool:
        elapsed = 0
        saw_delete_in_progress = False
        while elapsed < STACK_DELETE_TIMEOUT:
            status = self.get_stack_status(stack_name)
            if status is None or status == "DELETE_COMPLETE":
                success(f"Stack {stack_name} deleted")
                return True
            if status == "DELETE_FAILED":
                error(f"Stack {stack_name} deletion failed")
                return False
            if "DELETE" in (status or ""):
                saw_delete_in_progress = True
            elif saw_delete_in_progress:
                # Stack reverted from DELETE_IN_PROGRESS to a non-delete
                # state — CloudFormation canceled the delete (typically
                # due to cross-stack export still in use).
                error(
                    f"Stack {stack_name} delete was canceled "
                    f"(reverted to {status}). A dependent stack likely "
                    f"still imports its exports."
                )
                return False
            time.sleep(STACK_DELETE_POLL_INTERVAL)
            elapsed += STACK_DELETE_POLL_INTERVAL
            if elapsed % 60 == 0:
                info(
                    f"  Waiting for {stack_name}... "
                    f"({elapsed}s elapsed, status: {status})"
                )
        error(
            f"Timeout waiting for {stack_name} deletion " f"({STACK_DELETE_TIMEOUT}s)"
        )
        return False

    def deploy_stack(
        self,
        stack_name: str,
        template: str,
        params: Dict[str, str],
        tags: Dict[str, str],
        dry_run: bool = True,
    ) -> bool:
        if dry_run:
            info(f"[DRY-RUN] Would deploy stack: {stack_name}")
            info(f"  Template: {template}")
            info(f"  Parameters: {json.dumps(params, indent=4)}")
            return True

        info(f"Deploying stack: {stack_name}")
        cmd = [
            "aws",
            "cloudformation",
            "deploy",
            "--stack-name",
            stack_name,
            "--template-file",
            template,
            "--parameter-overrides",
        ]
        cmd.extend(f"{k}={v}" for k, v in params.items())
        cmd.extend(
            [
                "--capabilities",
                "CAPABILITY_NAMED_IAM",
                "--tags",
                f"Project={PROJECT_NAME}",
                f"Environment={ENVIRONMENT}",
                f"Layer={tags.get('Layer', 'unknown')}",
                "--region",
                self.region,
                "--no-fail-on-empty-changeset",
            ]
        )
        info(f"  Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if result.returncode == 0:
            success(f"Stack {stack_name} deployed successfully")
            return True
        if (
            "No changes to deploy" in result.stdout
            or "No updates are to be performed" in result.stderr
        ):
            success(f"Stack {stack_name} already up to date")
            return True
        error(f"Stack {stack_name} deploy failed (exit {result.returncode})")
        if result.stderr:
            error(f"  stderr: {result.stderr.strip()}")
        return False


# ---------------------------------------------------------------------------
# Neptune Snapshot Manager
# ---------------------------------------------------------------------------


class NeptuneSnapshotManager:
    """Manages Neptune cluster snapshots for safe teardown."""

    def __init__(self, neptune_client):
        self.neptune = neptune_client
        self.cluster_id = f"{PROJECT_NAME}-neptune-{ENVIRONMENT}"

    def create_snapshot(self, dry_run: bool = True) -> Optional[str]:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        snapshot_id = f"{self.cluster_id}-ks-{ts}"

        if dry_run:
            info(f"[DRY-RUN] Would create Neptune snapshot: {snapshot_id}")
            return snapshot_id

        info(f"Creating Neptune snapshot: {snapshot_id}")
        try:
            self.neptune.create_db_cluster_snapshot(
                DBClusterSnapshotIdentifier=snapshot_id,
                DBClusterIdentifier=self.cluster_id,
                Tags=[
                    {"Key": "KillSwitch", "Value": "true"},
                    {"Key": "Project", "Value": PROJECT_NAME},
                    {"Key": "Environment", "Value": ENVIRONMENT},
                ],
            )
        except ClientError as e:
            if "DBClusterNotFoundFault" in str(e):
                warn("Neptune cluster not found - skipping snapshot")
                return None
            raise

        elapsed = 0
        while elapsed < SNAPSHOT_TIMEOUT:
            try:
                resp = self.neptune.describe_db_cluster_snapshots(
                    DBClusterSnapshotIdentifier=snapshot_id
                )
                status = resp["DBClusterSnapshots"][0]["Status"]
                if status == "available":
                    success(f"Neptune snapshot ready: {snapshot_id}")
                    return snapshot_id
                info(f"  Snapshot status: {status} ({elapsed}s)")
            except ClientError:
                pass
            time.sleep(15)
            elapsed += 15

        error(f"Timeout waiting for Neptune snapshot ({SNAPSHOT_TIMEOUT}s)")
        return None

    def cleanup_old_snapshots(self, keep_latest: str, dry_run: bool = True) -> None:
        """Remove old kill-switch snapshots, keeping only the latest."""
        try:
            resp = self.neptune.describe_db_cluster_snapshots(
                DBClusterIdentifier=self.cluster_id,
                SnapshotType="manual",
            )
        except ClientError:
            return

        ks_snapshots = [
            s
            for s in resp.get("DBClusterSnapshots", [])
            if s["DBClusterSnapshotIdentifier"].startswith(f"{self.cluster_id}-ks-")
            and s["DBClusterSnapshotIdentifier"] != keep_latest
        ]

        for snap in ks_snapshots:
            sid = snap["DBClusterSnapshotIdentifier"]
            if dry_run:
                info(f"[DRY-RUN] Would delete old snapshot: {sid}")
            else:
                info(f"Deleting old snapshot: {sid}")
                try:
                    self.neptune.delete_db_cluster_snapshot(
                        DBClusterSnapshotIdentifier=sid
                    )
                except ClientError as e:
                    warn(f"Could not delete snapshot {sid}: {e}")


# ---------------------------------------------------------------------------
# EventBridge Schedule Manager
# ---------------------------------------------------------------------------


def disable_schedules(scheduler_client, dry_run: bool = True) -> List[str]:
    """Disable DEV EventBridge Scheduler rules."""
    disabled = []
    for schedule_name in EVENTBRIDGE_SCHEDULES:
        if dry_run:
            info(f"[DRY-RUN] Would disable schedule: {schedule_name}")
            disabled.append(schedule_name)
            continue
        try:
            schedule = scheduler_client.get_schedule(Name=schedule_name)
            scheduler_client.update_schedule(
                Name=schedule_name,
                ScheduleExpression=schedule["ScheduleExpression"],
                FlexibleTimeWindow=schedule["FlexibleTimeWindow"],
                Target=schedule["Target"],
                State="DISABLED",
            )
            success(f"Disabled schedule: {schedule_name}")
            disabled.append(schedule_name)
        except ClientError as e:
            if "ResourceNotFoundException" in str(e):
                warn(f"Schedule {schedule_name} not found (skipping)")
            else:
                error(f"Failed to disable {schedule_name}: {e}")
    return disabled


def enable_schedules(scheduler_client, dry_run: bool = True) -> None:
    """Re-enable DEV EventBridge Scheduler rules."""
    for schedule_name in EVENTBRIDGE_SCHEDULES:
        if dry_run:
            info(f"[DRY-RUN] Would enable schedule: {schedule_name}")
            continue
        try:
            schedule = scheduler_client.get_schedule(Name=schedule_name)
            scheduler_client.update_schedule(
                Name=schedule_name,
                ScheduleExpression=schedule["ScheduleExpression"],
                FlexibleTimeWindow=schedule["FlexibleTimeWindow"],
                Target=schedule["Target"],
                State="ENABLED",
            )
            success(f"Enabled schedule: {schedule_name}")
        except ClientError as e:
            if "ResourceNotFoundException" in str(e):
                warn(f"Schedule {schedule_name} not found (skipping)")
            else:
                error(f"Failed to enable {schedule_name}: {e}")


# ---------------------------------------------------------------------------
# CodeBuild Trigger (for upper-layer restore)
# ---------------------------------------------------------------------------


def trigger_codebuild_restores(codebuild_client, dry_run: bool = True) -> List[str]:
    """Trigger CodeBuild projects for upper-layer stack restoration.

    Returns list of build IDs for monitoring.
    """
    build_ids = []
    for project_name in CODEBUILD_RESTORE_PROJECTS:
        if dry_run:
            info(f"[DRY-RUN] Would trigger CodeBuild: {project_name}")
            continue
        try:
            resp = codebuild_client.start_build(
                projectName=project_name,
                environmentVariablesOverride=[
                    {
                        "name": "TRIGGERED_BY",
                        "value": "dev-killswitch-restore",
                        "type": "PLAINTEXT",
                    },
                ],
            )
            build_id = resp["build"]["id"]
            build_ids.append(build_id)
            success(f"Triggered {project_name}: {build_id}")
        except ClientError as e:
            if "ResourceNotFoundException" in str(e):
                warn(f"CodeBuild project {project_name} not found")
            else:
                error(f"Failed to trigger {project_name}: {e}")
    return build_ids


# ---------------------------------------------------------------------------
# SNS Notifications
# ---------------------------------------------------------------------------


def send_notification(
    sns_client,
    action: str,
    details: Dict[str, Any],
    dry_run: bool = True,
) -> None:
    if dry_run:
        info(f"[DRY-RUN] Would send SNS notification: DEV {action}")
        return
    try:
        resp = sns_client.list_topics()
        topic_arn = None
        for topic in resp.get("Topics", []):
            if SNS_TOPIC_NAME in topic["TopicArn"]:
                topic_arn = topic["TopicArn"]
                break
        if not topic_arn:
            warn(f"SNS topic {SNS_TOPIC_NAME} not found - " f"skipping notification")
            return

        message = {
            "action": action,
            "environment": ENVIRONMENT,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=f"[Aura DEV] Kill-Switch {action.upper()}",
            Message=json.dumps(message, indent=2, default=str),
        )
        success(f"SNS notification sent: {action}")
    except ClientError as e:
        warn(f"Could not send SNS notification: {e}")


# ---------------------------------------------------------------------------
# Parameter Resolution
# ---------------------------------------------------------------------------


def resolve_parameters(sm: StackManager, ssm_client) -> Dict[str, str]:
    """Resolve all parameters from foundation stacks for restore deploys."""
    params: Dict[str, str] = {}

    # From networking stack
    net_stack = FOUNDATION_STACKS["networking"]
    params["VPC_ID"] = sm.get_stack_output(net_stack, "VpcId") or ""
    params["PRIVATE_SUBNET_IDS"] = (
        sm.get_stack_output(net_stack, "PrivateSubnetIds") or ""
    )
    params["PUBLIC_SUBNET_IDS"] = (
        sm.get_stack_output(net_stack, "PublicSubnetIds") or ""
    )
    params["VPC_CIDR"] = sm.get_stack_output(net_stack, "VpcCidr") or "10.0.0.0/16"
    params["PRIVATE_SUBNET_1"] = (
        sm.get_stack_output(net_stack, "PrivateSubnet1Id") or ""
    )
    params["PRIVATE_SUBNET_2"] = (
        sm.get_stack_output(net_stack, "PrivateSubnet2Id") or ""
    )

    # From security stack
    sec_stack = FOUNDATION_STACKS["security"]
    params["NEPTUNE_SG"] = (
        sm.get_stack_output(sec_stack, "NeptuneSecurityGroupId") or ""
    )
    params["OPENSEARCH_SG"] = (
        sm.get_stack_output(sec_stack, "OpenSearchSecurityGroupId") or ""
    )
    params["EKS_SG"] = sm.get_stack_output(sec_stack, "EKSSecurityGroupId") or ""
    params["EKS_NODE_SG"] = (
        sm.get_stack_output(sec_stack, "EKSNodeSecurityGroupId") or ""
    )
    params["VPCE_SG"] = (
        sm.get_stack_output(sec_stack, "VPCEndpointSecurityGroupId") or ""
    )

    # From IAM stack
    iam_stack = FOUNDATION_STACKS["iam"]
    params["EKS_CLUSTER_ROLE"] = (
        sm.get_stack_output(iam_stack, "EKSClusterRoleArn") or ""
    )
    params["EKS_NODE_ROLE"] = sm.get_stack_output(iam_stack, "EKSNodeRoleArn") or ""

    # AdminRoleArn from SSM Parameter Store
    try:
        resp = ssm_client.get_parameter(
            Name=f"/{PROJECT_NAME}/{ENVIRONMENT}/admin-role-arn",
            WithDecryption=True,
        )
        params["ADMIN_ROLE_ARN"] = resp["Parameter"]["Value"]
    except ClientError:
        params["ADMIN_ROLE_ARN"] = ""

    # Route tables for VPC endpoints (queried via EC2)
    ec2 = boto3.client("ec2", region_name=sm.region)
    for suffix in ["1", "2"]:
        try:
            resp = ec2.describe_route_tables(
                Filters=[
                    {
                        "Name": "tag:Name",
                        "Values": [
                            f"{PROJECT_NAME}-private-rt-{suffix}-" f"{ENVIRONMENT}"
                        ],
                    }
                ]
            )
            rts = resp.get("RouteTables", [])
            params[f"PRIVATE_RT_{suffix}"] = rts[0]["RouteTableId"] if rts else ""
        except ClientError:
            params[f"PRIVATE_RT_{suffix}"] = ""
    params["PRIVATE_ROUTE_TABLE_IDS"] = ",".join(
        filter(
            None,
            [
                params.get("PRIVATE_RT_1", ""),
                params.get("PRIVATE_RT_2", ""),
            ],
        )
    )

    return params


# ---------------------------------------------------------------------------
# Restore: per-stack deploy configs (core 9 stacks only)
# ---------------------------------------------------------------------------


def _build_deploy_configs(params: Dict[str, str]) -> Dict[str, Dict]:
    """Build CloudFormation deploy parameters for core infrastructure.

    These 9 stacks are deployed directly by the kill-switch (matching
    the QA kill-switch pattern). Upper-layer stacks are restored via
    CodeBuild triggers.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return {
        # VPC Endpoints (Phase 1 of restore)
        f"{PROJECT_NAME}-vpc-endpoints-{ENVIRONMENT}": {
            "template": "deploy/cloudformation/vpc-endpoints.yaml",
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "VpcId": params["VPC_ID"],
                "PrivateSubnetIds": (f'"{params["PRIVATE_SUBNET_IDS"]}"'),
                "PrivateRouteTableIds": (f'"{params["PRIVATE_ROUTE_TABLE_IDS"]}"'),
                "VPCEndpointSecurityGroupId": params["VPCE_SG"],
            },
            "tags": {"Layer": "foundation", "DeployTimestamp": ts},
        },
        # Neptune (Phase 2)
        f"{PROJECT_NAME}-neptune-{ENVIRONMENT}": {
            "template": ("deploy/cloudformation/neptune-simplified.yaml"),
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "PrivateSubnetIds": (f'"{params["PRIVATE_SUBNET_IDS"]}"'),
                "NeptuneSecurityGroupId": params["NEPTUNE_SG"],
                "NeptuneMode": "provisioned",
                "InstanceType": "db.t3.medium",
            },
            "tags": {"Layer": "data", "DeployTimestamp": ts},
        },
        # OpenSearch (Phase 2)
        f"{PROJECT_NAME}-opensearch-{ENVIRONMENT}": {
            "template": "deploy/cloudformation/opensearch.yaml",
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "VpcId": params["VPC_ID"],
                "PrivateSubnetIds": (f'"{params["PRIVATE_SUBNET_IDS"]}"'),
                "OpenSearchSecurityGroupId": params["OPENSEARCH_SG"],
                "InstanceType": "t3.small.search",
            },
            "tags": {"Layer": "data", "DeployTimestamp": ts},
        },
        # ElastiCache (Phase 2)
        f"{PROJECT_NAME}-elasticache-{ENVIRONMENT}": {
            "template": "deploy/cloudformation/elasticache.yaml",
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "PrivateSubnetIds": (f'"{params["PRIVATE_SUBNET_IDS"]}"'),
                "NodeSecurityGroupId": params["EKS_NODE_SG"],
            },
            "tags": {"Layer": "data", "DeployTimestamp": ts},
        },
        # EKS Cluster (Phase 3)
        f"{PROJECT_NAME}-eks-{ENVIRONMENT}": {
            "template": "deploy/cloudformation/eks.yaml",
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "PrivateSubnetIds": (f'"{params["PUBLIC_SUBNET_IDS"]}"'),
                "EKSSecurityGroupId": params["EKS_SG"],
                "EKSClusterRoleArn": params["EKS_CLUSTER_ROLE"],
                "AdminRoleArn": params["ADMIN_ROLE_ARN"],
                "KubernetesVersion": "1.34",
            },
            "tags": {"Layer": "compute", "DeployTimestamp": ts},
        },
        # General Node Group (Phase 4)
        f"{PROJECT_NAME}-nodegroup-general-{ENVIRONMENT}": {
            "template": ("deploy/cloudformation/eks-nodegroup-general.yaml"),
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "ClusterName": (f"{PROJECT_NAME}-cluster-{ENVIRONMENT}"),
                "NodeRoleArn": params["EKS_NODE_ROLE"],
                "PrivateSubnetIds": (f'"{params["PUBLIC_SUBNET_IDS"]}"'),
                "NodeSecurityGroupId": params["EKS_NODE_SG"],
                "InstanceTypes": '"t3.large,t3a.large,t3.xlarge"',
                "MinSize": "2",
                "MaxSize": "6",
                "DesiredSize": "2",
                "CapacityType": "SPOT",
                "KubernetesVersion": "1.34",
            },
            "tags": {
                "Layer": "compute",
                "NodeGroupType": "general-purpose",
                "DeployTimestamp": ts,
            },
        },
        # Memory Node Group (Phase 4)
        f"{PROJECT_NAME}-nodegroup-memory-{ENVIRONMENT}": {
            "template": ("deploy/cloudformation/eks-nodegroup-memory.yaml"),
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "ClusterName": (f"{PROJECT_NAME}-cluster-{ENVIRONMENT}"),
                "NodeRoleArn": params["EKS_NODE_ROLE"],
                "PrivateSubnetIds": (f'"{params["PUBLIC_SUBNET_IDS"]}"'),
                "NodeSecurityGroupId": params["EKS_NODE_SG"],
                "InstanceTypes": '"r6i.xlarge,r5.xlarge,r6a.xlarge"',
                "MinSize": "1",
                "MaxSize": "3",
                "DesiredSize": "1",
                "KubernetesVersion": "1.34",
            },
            "tags": {
                "Layer": "compute",
                "NodeGroupType": "memory-optimized",
                "DeployTimestamp": ts,
            },
        },
        # GPU Node Group (Phase 4)
        f"{PROJECT_NAME}-nodegroup-gpu-{ENVIRONMENT}": {
            "template": ("deploy/cloudformation/eks-nodegroup-gpu.yaml"),
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "ClusterName": (f"{PROJECT_NAME}-cluster-{ENVIRONMENT}"),
                "NodeRoleArn": params["EKS_NODE_ROLE"],
                "PrivateSubnetIds": (f'"{params["PUBLIC_SUBNET_IDS"]}"'),
                "NodeSecurityGroupId": params["EKS_NODE_SG"],
                "InstanceTypes": '"g5.xlarge,g4dn.xlarge"',
                "MinSize": "0",
                "MaxSize": "2",
                "DesiredSize": "0",
                "CapacityType": "SPOT",
                "KubernetesVersion": "1.34",
            },
            "tags": {
                "Layer": "compute",
                "NodeGroupType": "gpu-compute",
                "DeployTimestamp": ts,
            },
        },
        # Network Services (Phase 4)
        f"{PROJECT_NAME}-network-services-{ENVIRONMENT}": {
            "template": ("deploy/cloudformation/network-services.yaml"),
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "VpcId": params["VPC_ID"],
                "PrivateSubnet1Id": params["PRIVATE_SUBNET_1"],
                "PrivateSubnet2Id": params["PRIVATE_SUBNET_2"],
                "VpcCidr": params["VPC_CIDR"],
                "AllowedCidr": params["VPC_CIDR"],
            },
            "tags": {
                "Layer": "network-services",
                "DeployTimestamp": ts,
            },
        },
    }


# ---------------------------------------------------------------------------
# Pre-flight Checks
# ---------------------------------------------------------------------------


def pre_flight_checks(sts_client, codebuild_client, region: str) -> Dict[str, str]:
    """Validate environment and credentials."""
    if ENVIRONMENT not in ALLOWED_ENVIRONMENTS:
        error(
            f"Environment '{ENVIRONMENT}' not in allowed set: "
            f"{ALLOWED_ENVIRONMENTS}"
        )
        sys.exit(2)

    # Verify caller identity
    try:
        identity = sts_client.get_caller_identity()
    except (NoCredentialsError, ClientError) as e:
        error(f"AWS credentials not available: {e}")
        sys.exit(2)

    account_id = identity["Account"]
    caller_arn = identity["Arn"]

    # Validate account ID if expected value is set
    expected_account = os.environ.get("AURA_DEV_ACCOUNT_ID")
    if expected_account and account_id != expected_account:
        error(f"Account ID mismatch: expected {expected_account}, " f"got {account_id}")
        sys.exit(2)
    info(f"AWS Account: {account_id}")
    info(f"Caller: {caller_arn}")

    # Validate all stack names contain -dev (defense in depth)
    for stack_def in STACK_DEFINITIONS:
        if f"-{ENVIRONMENT}" not in stack_def["name"]:
            error(
                f"Stack name {stack_def['name']} does not contain " f"'-{ENVIRONMENT}'"
            )
            sys.exit(2)

    # Validate no stack in STACK_DEFINITIONS is in PROTECTED_STACKS
    for stack_def in STACK_DEFINITIONS:
        if stack_def["name"] in PROTECTED_STACKS:
            error(
                f"Stack {stack_def['name']} is in both "
                f"STACK_DEFINITIONS and PROTECTED_STACKS"
            )
            sys.exit(2)

    # Check no CodeBuild builds are running for DEV
    dev_projects = [
        f"{PROJECT_NAME}-data-deploy-{ENVIRONMENT}",
        f"{PROJECT_NAME}-compute-deploy-{ENVIRONMENT}",
        f"{PROJECT_NAME}-foundation-deploy-{ENVIRONMENT}",
        f"{PROJECT_NAME}-application-deploy-{ENVIRONMENT}",
        f"{PROJECT_NAME}-observability-deploy-{ENVIRONMENT}",
        f"{PROJECT_NAME}-serverless-deploy-{ENVIRONMENT}",
        f"{PROJECT_NAME}-sandbox-deploy-{ENVIRONMENT}",
        f"{PROJECT_NAME}-security-deploy-{ENVIRONMENT}",
    ]
    for project_name in dev_projects:
        try:
            resp = codebuild_client.list_builds_for_project(
                projectName=project_name, sortOrder="DESCENDING"
            )
            build_ids = resp.get("ids", [])[:1]
            if build_ids:
                builds = codebuild_client.batch_get_builds(ids=build_ids)
                for build in builds.get("builds", []):
                    if build["buildStatus"] == "IN_PROGRESS":
                        error(
                            f"CodeBuild project {project_name} has a "
                            f"build in progress. Wait for it to "
                            f"complete before running kill-switch."
                        )
                        sys.exit(1)
        except ClientError:
            pass  # Project may not exist

    success("Pre-flight checks passed")
    return {"account_id": account_id, "caller_arn": caller_arn}


# ---------------------------------------------------------------------------
# Main Operations
# ---------------------------------------------------------------------------


def do_shutdown(args: argparse.Namespace) -> int:
    """Execute the DEV environment shutdown sequence."""
    dry_run = not args.execute
    region = args.region

    session = boto3.Session(region_name=region)
    sts = session.client("sts")
    cfn = session.client("cloudformation")
    neptune = session.client("neptune")
    scheduler = session.client("scheduler")
    sns = session.client("sns")
    s3 = session.client("s3")
    codebuild = session.client("codebuild")

    sm = StackManager(cfn, region)
    nsm = NeptuneSnapshotManager(neptune)

    if dry_run:
        info(
            f"{BOLD}=== DRY-RUN MODE "
            f"(use --execute to perform real operations) ==={NC}\n"
        )

    # Pre-flight
    phase_header(0, "Pre-flight Checks")
    identity = pre_flight_checks(sts, codebuild, region)

    # Confirmation prompt
    if args.execute and not args.force:
        total = len(STACK_DEFINITIONS)
        stacks_by_layer = {}
        for s in STACK_DEFINITIONS:
            stacks_by_layer.setdefault(s["layer"], []).append(s["name"])
        print(
            f"\n{RED}{BOLD}WARNING: This will DELETE {total} DEV "
            f"CloudFormation stacks:{NC}"
        )
        for layer, names in stacks_by_layer.items():
            print(f"\n  {BOLD}{layer} ({len(names)} stacks):{NC}")
            for name in names:
                print(f"    - {name}")
        print("\n  Estimated monthly savings: significant monthly savings")
        print("  Estimated shutdown time: ~60-90 minutes")
        print("  Estimated restore time: ~90-120 minutes\n")
        confirm = input(f"  Type '{RED}DESTROY DEV{NC}' to confirm: ")
        if confirm.strip() != "DESTROY DEV":
            error("Confirmation failed - aborting")
            return 1

    # Initialize state
    state = KillSwitchState(
        status="partial",
        shutdown_timestamp=datetime.now(timezone.utc).isoformat(),
        shutdown_by=identity["caller_arn"],
    )

    # Neptune snapshot
    if not args.skip_snapshot:
        phase_header(0, "Neptune Snapshot")
        snapshot_id = nsm.create_snapshot(dry_run=dry_run)
        if snapshot_id is None and not dry_run:
            warn("Neptune snapshot skipped (cluster not found)")
        state.neptune_snapshot_id = snapshot_id
    else:
        info("Skipping Neptune snapshot (--skip-snapshot)")

    # Phase 1: Disable schedulers
    phase_header(1, "Disable EventBridge Schedules")
    state.disabled_schedules = disable_schedules(scheduler, dry_run=dry_run)

    # Phases 2-12: Delete stacks by phase
    # Within each phase, stacks are grouped by delete_order (default 1).
    # Stacks with the same delete_order run in parallel; groups run
    # sequentially from lowest to highest to respect cross-stack exports.
    phases = sorted(set(s["phase"] for s in STACK_DEFINITIONS))
    for phase_num in phases:
        phase_stacks = [s for s in STACK_DEFINITIONS if s["phase"] == phase_num]
        phase_name = phase_stacks[0]["layer"]
        phase_header(
            phase_num,
            f"Delete {phase_name} stacks ({len(phase_stacks)})",
        )

        # Group stacks by delete_order (default 1 = all parallel)
        order_groups: dict[int, list[dict]] = {}
        for s in phase_stacks:
            order = s.get("delete_order", 1)
            order_groups.setdefault(order, []).append(s)

        for order_key in sorted(order_groups):
            group = order_groups[order_key]
            if len(order_groups) > 1:
                info(
                    f"Delete group {order_key}: "
                    f"{', '.join(s['name'] for s in group)}"
                )

            if len(group) == 1:
                stack_def = group[0]
                ok = sm.delete_stack(stack_def["name"], dry_run=dry_run)
                if ok:
                    state.deleted_stacks.append(
                        asdict(
                            DeletedStack(
                                stack_name=stack_def["name"],
                                template_file=stack_def["template"],
                                deleted_at=datetime.now(timezone.utc).isoformat(),
                            )
                        )
                    )
            else:
                with ThreadPoolExecutor(max_workers=len(group)) as executor:
                    futures = {
                        executor.submit(sm.delete_stack, s["name"], dry_run): s
                        for s in group
                    }
                    for future in as_completed(futures):
                        stack_def = futures[future]
                        try:
                            ok = future.result()
                            if ok:
                                state.deleted_stacks.append(
                                    asdict(
                                        DeletedStack(
                                            stack_name=stack_def["name"],
                                            template_file=stack_def["template"],
                                            deleted_at=datetime.now(
                                                timezone.utc
                                            ).isoformat(),
                                        )
                                    )
                                )
                        except Exception as e:
                            error(f"Error deleting {stack_def['name']}: {e}")

        state.phases_completed.append(phase_num)

    # Cleanup old snapshots
    if state.neptune_snapshot_id and not args.skip_snapshot:
        phase_header(13, "Cleanup Old Snapshots")
        nsm.cleanup_old_snapshots(state.neptune_snapshot_id, dry_run=dry_run)

    # Finalize
    phase_header(14, "Finalize")
    expected_stacks = len(STACK_DEFINITIONS)
    actual_deleted = len(state.deleted_stacks)
    if actual_deleted >= expected_stacks:
        state.status = "shutdown"
    else:
        state.status = "partial"
        warn(f"Partial shutdown: {actual_deleted}/{expected_stacks} " f"stacks deleted")

    save_state(state, s3, cfn)
    send_notification(
        sns,
        "shutdown",
        {
            "deleted_stacks": [s["stack_name"] for s in state.deleted_stacks],
            "neptune_snapshot": state.neptune_snapshot_id,
            "operator": identity["caller_arn"],
        },
        dry_run=dry_run,
    )

    # Summary
    label = "Plan" if dry_run else "Complete"
    print(f"\n{GREEN}{BOLD}=== Shutdown {label} ==={NC}")
    print(
        f"  Stacks {'to delete' if dry_run else 'deleted'}: "
        f"{actual_deleted}/{expected_stacks}"
    )
    print(f"  Neptune snapshot: " f"{state.neptune_snapshot_id or 'skipped'}")
    print(f"  Schedules disabled: {len(state.disabled_schedules)}")
    print("  Estimated monthly savings: significant monthly savings")
    if dry_run:
        print(f"\n  {YELLOW}Run with --execute to perform " f"these operations{NC}")
    return 0 if state.status == "shutdown" or dry_run else 1


def do_restore(args: argparse.Namespace) -> int:
    """Execute the DEV environment restore sequence.

    Phase 1-4: Deploy core infrastructure directly (9 stacks).
    Phase 5: Trigger CodeBuild for upper layers.
    Phase 6: Re-enable EventBridge schedules.
    """
    dry_run = not args.execute
    region = args.region

    session = boto3.Session(region_name=region)
    sts = session.client("sts")
    cfn = session.client("cloudformation")
    scheduler = session.client("scheduler")
    sns = session.client("sns")
    s3 = session.client("s3")
    ssm = session.client("ssm")
    codebuild = session.client("codebuild")

    sm = StackManager(cfn, region)

    if dry_run:
        info(
            f"{BOLD}=== DRY-RUN MODE "
            f"(use --execute to perform real operations) ==={NC}\n"
        )

    # Pre-flight
    phase_header(0, "Pre-flight Checks")
    identity = pre_flight_checks(sts, codebuild, region)

    # Load state
    state = load_state(s3, cfn)
    if state.status == "running":
        warn("State file indicates DEV is already running")
    if state.neptune_snapshot_id:
        info(f"Neptune snapshot available: {state.neptune_snapshot_id}")

    # Resolve parameters
    phase_header(0, "Resolve Parameters")
    params = resolve_parameters(sm, ssm)
    missing = [k for k, v in params.items() if not v and k not in ("ADMIN_ROLE_ARN",)]
    if missing:
        error(f"Missing foundation parameters: {missing}")
        error("Ensure foundation stacks (networking, security, iam) " "are deployed")
        return 1
    success(f"Resolved {len(params)} parameters from foundation stacks")

    if args.verbose:
        for k, v in sorted(params.items()):
            info(f"  {k} = {v}")

    # Build deploy configs (core 9 stacks)
    deploy_configs = _build_deploy_configs(params)

    # Confirmation
    if args.execute and not args.force:
        print(f"\n{CYAN}{BOLD}This will RESTORE the DEV environment:{NC}")
        print(f"\n  {BOLD}Core infrastructure (direct deploy):{NC}")
        for name in deploy_configs:
            print(f"    + {name}")
        print(f"\n  {BOLD}Upper layers (CodeBuild triggers):{NC}")
        for project in CODEBUILD_RESTORE_PROJECTS:
            print(f"    ~ {project}")
        print("\n  Estimated deploy time: ~90-120 minutes\n")
        confirm = input(f"  Type '{GREEN}RESTORE DEV{NC}' to confirm: ")
        if confirm.strip() != "RESTORE DEV":
            error("Confirmation failed - aborting")
            return 1

    # Restore phases (order matters)
    restore_order = [
        (
            1,
            "VPC Endpoints",
            [f"{PROJECT_NAME}-vpc-endpoints-{ENVIRONMENT}"],
        ),
        (
            2,
            "Data Stores",
            [
                f"{PROJECT_NAME}-neptune-{ENVIRONMENT}",
                f"{PROJECT_NAME}-opensearch-{ENVIRONMENT}",
                f"{PROJECT_NAME}-elasticache-{ENVIRONMENT}",
            ],
        ),
        (
            3,
            "EKS Control Plane",
            [f"{PROJECT_NAME}-eks-{ENVIRONMENT}"],
        ),
        (
            4,
            "EKS Node Groups + Services",
            [
                f"{PROJECT_NAME}-nodegroup-general-{ENVIRONMENT}",
                f"{PROJECT_NAME}-nodegroup-memory-{ENVIRONMENT}",
                f"{PROJECT_NAME}-nodegroup-gpu-{ENVIRONMENT}",
                f"{PROJECT_NAME}-network-services-{ENVIRONMENT}",
            ],
        ),
    ]

    deploy_failures = 0

    for phase_num, phase_name, stack_names in restore_order:
        phase_header(phase_num, f"Deploy {phase_name}")

        # After EKS cluster deploys, resolve ClusterName for node groups
        if phase_num == 4 and not dry_run:
            cluster_name = sm.get_stack_output(
                f"{PROJECT_NAME}-eks-{ENVIRONMENT}", "ClusterName"
            )
            if cluster_name:
                for ng_name in stack_names:
                    if "nodegroup" in ng_name and ng_name in deploy_configs:
                        deploy_configs[ng_name]["params"]["ClusterName"] = cluster_name

        if len(stack_names) == 1:
            name = stack_names[0]
            cfg = deploy_configs.get(name)
            if cfg:
                ok = sm.deploy_stack(
                    name,
                    cfg["template"],
                    cfg["params"],
                    cfg["tags"],
                    dry_run=dry_run,
                )
                if not ok:
                    deploy_failures += 1
        else:
            with ThreadPoolExecutor(max_workers=len(stack_names)) as executor:
                futures = {}
                for name in stack_names:
                    cfg = deploy_configs.get(name)
                    if cfg:
                        futures[
                            executor.submit(
                                sm.deploy_stack,
                                name,
                                cfg["template"],
                                cfg["params"],
                                cfg["tags"],
                                dry_run,
                            )
                        ] = name
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        ok = future.result()
                        if not ok:
                            deploy_failures += 1
                    except Exception as e:
                        error(f"Error deploying {name}: {e}")
                        deploy_failures += 1

    # Phase 5: Trigger CodeBuild for upper layers
    phase_header(5, "Trigger CodeBuild for Upper Layers")
    build_ids = trigger_codebuild_restores(codebuild, dry_run=dry_run)
    state.codebuild_restore_ids = build_ids

    # Phase 6: Re-enable schedules
    phase_header(6, "Re-enable EventBridge Schedules")
    enable_schedules(scheduler, dry_run=dry_run)

    # Finalize
    phase_header(7, "Finalize")
    if deploy_failures > 0:
        state.status = "partial"
        warn(f"Restore had {deploy_failures} failure(s)")
    else:
        state.status = "running"
    state.restore_timestamp = datetime.now(timezone.utc).isoformat()
    state.restore_by = identity["caller_arn"]
    state.phases_completed = []
    save_state(state, s3, cfn)
    send_notification(
        sns,
        "restore",
        {
            "restored_stacks": list(deploy_configs.keys()),
            "codebuild_triggers": CODEBUILD_RESTORE_PROJECTS,
            "operator": identity["caller_arn"],
        },
        dry_run=dry_run,
    )

    # Summary
    label = "Plan" if dry_run else "Complete"
    print(f"\n{GREEN}{BOLD}=== Restore {label} ==={NC}")
    print(
        f"  Core stacks {'to deploy' if dry_run else 'deployed'}: "
        f"{len(deploy_configs)}"
    )
    print(
        f"  CodeBuild projects "
        f"{'to trigger' if dry_run else 'triggered'}: "
        f"{len(CODEBUILD_RESTORE_PROJECTS)}"
    )
    if build_ids:
        print(f"  Build IDs: {', '.join(build_ids)}")
        print(
            f"\n  {YELLOW}Monitor CodeBuild builds for upper layer "
            f"deployment status{NC}"
        )
    if deploy_failures > 0:
        print(f"  {RED}Failures: {deploy_failures}{NC}")
    if dry_run:
        print(f"\n  {YELLOW}Run with --execute to perform " f"these operations{NC}")
    return 0 if deploy_failures == 0 or dry_run else 1


def do_status(args: argparse.Namespace) -> int:
    """Show current status of all DEV stacks."""
    region = args.region
    session = boto3.Session(region_name=region)
    cfn = session.client("cloudformation")
    s3 = session.client("s3")

    sm = StackManager(cfn, region)

    print(f"\n{BOLD}DEV Environment Status{NC}")
    print(f"{'=' * 60}")

    # Stack statuses
    print(f"\n{BOLD}CloudFormation Stacks ({len(STACK_DEFINITIONS)}):{NC}")
    total_cost = 0.0
    cost_map = {
        "neptune": 75,
        "opensearch": 70,
        "eks-dev": 73,
        "nodegroup-general": 30,
        "nodegroup-memory": 18,
        "nodegroup-gpu": 0,
        "network-services": 40,
        "vpc-endpoints": 65,
        "elasticache": 12,
        "config-compliance": 36,
        "guardduty": 30,
        "sandbox": 50,
        "ssr-training-dev": 30,
        "red-team": 10,
    }
    for stack_def in STACK_DEFINITIONS:
        name = stack_def["name"]
        status = sm.get_stack_status(name)
        display_status = status or "DOES NOT EXIST"

        if status and "COMPLETE" in status and "DELETE" not in status:
            color = GREEN
            for key, cost in cost_map.items():
                if key in name:
                    total_cost += cost
                    break
        elif status is None or "DELETE" in (status or ""):
            color = RED
        else:
            color = YELLOW

        cost_str = ""
        for key, cost in cost_map.items():
            if key in name:
                cost_str = f" (~${cost}/mo)" if cost > 0 else ""
                break

        print(f"  {color}{display_status:30s}{NC} {name}{cost_str}")

    print(
        f"\n  {BOLD}Estimated monthly cost of running stacks: "
        f"~${total_cost:.0f}{NC}"
    )

    # EventBridge schedules
    print(f"\n{BOLD}EventBridge Schedules:{NC}")
    try:
        scheduler = session.client("scheduler")
        for schedule_name in EVENTBRIDGE_SCHEDULES:
            try:
                schedule = scheduler.get_schedule(Name=schedule_name)
                sched_state = schedule.get("State", "UNKNOWN")
                color = GREEN if sched_state == "ENABLED" else RED
                print(f"  {color}{sched_state:30s}{NC} {schedule_name}")
            except ClientError:
                print(f"  {RED}{'NOT FOUND':30s}{NC} {schedule_name}")
    except ClientError as e:
        warn(f"Could not check schedules: {e}")

    # State file
    print(f"\n{BOLD}Kill-Switch State:{NC}")
    state = load_state(s3, cfn)
    print(f"  Status: {state.status}")
    if state.shutdown_timestamp:
        print(f"  Last shutdown: {state.shutdown_timestamp}")
        print(f"  Shutdown by: {state.shutdown_by}")
    if state.neptune_snapshot_id:
        print(f"  Neptune snapshot: {state.neptune_snapshot_id}")
    if state.restore_timestamp:
        print(f"  Last restore: {state.restore_timestamp}")
    if state.codebuild_restore_ids:
        print(f"  CodeBuild restores: " f"{', '.join(state.codebuild_restore_ids)}")

    print()
    return 0


# ---------------------------------------------------------------------------
# Post-Shutdown Cost Cleanup
# ---------------------------------------------------------------------------

# Tags that identify Kubernetes-managed load balancers
K8S_ELB_TAGS = frozenset(
    [
        "kubernetes.io/cluster/aura-cluster-dev",
        "ingress.k8s.aws/stack",
        "elbv2.k8s.aws/cluster",
    ]
)

KMS_STACK_NAME = f"{PROJECT_NAME}-kms-{ENVIRONMENT}"


def cleanup_orphaned_elbs(elbv2_client, elb_client, dry_run: bool = True) -> int:
    """Find and delete load balancers not managed by any CloudFormation stack.

    When EKS is deleted via CloudFormation, Kubernetes-managed ALBs (created
    by the AWS Load Balancer Controller) are NOT automatically deleted. This
    function finds and deletes them.

    Returns count of deleted/would-delete ELBs.
    """
    count = 0

    # Check ELBv2 (ALB/NLB) load balancers
    paginator = elbv2_client.get_paginator("describe_load_balancers")
    for page in paginator.paginate():
        for lb in page.get("LoadBalancers", []):
            lb_arn = lb["LoadBalancerArn"]
            lb_name = lb.get("LoadBalancerName", lb_arn)
            try:
                tag_resp = elbv2_client.describe_tags(ResourceArns=[lb_arn])
                tags = {}
                for desc in tag_resp.get("TagDescriptions", []):
                    for tag in desc.get("Tags", []):
                        tags[tag["Key"]] = tag.get("Value", "")
            except ClientError:
                tags = {}

            is_k8s = any(tag_key in tags for tag_key in K8S_ELB_TAGS)
            if is_k8s:
                if dry_run:
                    info(f"[DRY-RUN] Would delete ELBv2 load balancer: " f"{lb_name}")
                else:
                    info(f"Deleting ELBv2 load balancer: {lb_name}")
                    try:
                        # Delete listeners first
                        listeners = elbv2_client.describe_listeners(
                            LoadBalancerArn=lb_arn
                        )
                        for listener in listeners.get("Listeners", []):
                            elbv2_client.delete_listener(
                                ListenerArn=listener["ListenerArn"]
                            )
                        elbv2_client.delete_load_balancer(LoadBalancerArn=lb_arn)
                        success(f"Deleted ELBv2 load balancer: {lb_name}")
                    except ClientError as e:
                        error(f"Failed to delete ELBv2 {lb_name}: {e}")
                count += 1

    # Check Classic ELBs
    try:
        classic_resp = elb_client.describe_load_balancers()
        classic_lbs = classic_resp.get("LoadBalancerDescriptions", [])
    except ClientError:
        classic_lbs = []

    for lb in classic_lbs:
        lb_name = lb["LoadBalancerName"]
        try:
            tag_resp = elb_client.describe_tags(LoadBalancerNames=[lb_name])
            tags = {}
            for desc in tag_resp.get("TagDescriptions", []):
                for tag in desc.get("Tags", []):
                    tags[tag["Key"]] = tag.get("Value", "")
        except ClientError:
            tags = {}

        is_k8s = any(tag_key in tags for tag_key in K8S_ELB_TAGS)
        if is_k8s:
            if dry_run:
                info(f"[DRY-RUN] Would delete Classic ELB: {lb_name}")
            else:
                info(f"Deleting Classic ELB: {lb_name}")
                try:
                    elb_client.delete_load_balancer(LoadBalancerName=lb_name)
                    success(f"Deleted Classic ELB: {lb_name}")
                except ClientError as e:
                    error(f"Failed to delete Classic ELB {lb_name}: {e}")
            count += 1

    if count == 0:
        info("No orphaned Kubernetes load balancers found")
    return count


def cleanup_config_recorder(config_client, dry_run: bool = True) -> None:
    """Stop Config recorder, delete delivery channel, and delete all Config rules.

    The aura-compliance-settings-sync-dev protected stack keeps Config running.
    Stopping the recorder eliminates ongoing charges while the environment
    is hibernated. The recorder will be restarted when CodeBuild redeploys the
    compliance stack on restore.
    """
    # Stop configuration recorder
    try:
        recorders = config_client.describe_configuration_recorders()
        recorder_list = recorders.get("ConfigurationRecorders", [])
    except ClientError:
        recorder_list = []

    if not recorder_list:
        info("No Config recorder found - nothing to stop")
        return

    recorder_name = recorder_list[0]["name"]
    if dry_run:
        info(f"[DRY-RUN] Would stop Config recorder: {recorder_name}")
    else:
        try:
            config_client.stop_configuration_recorder(
                ConfigurationRecorderName=recorder_name
            )
            success(f"Stopped Config recorder: {recorder_name}")
        except ClientError as e:
            error(f"Failed to stop Config recorder: {e}")

    # Delete delivery channel
    try:
        channels = config_client.describe_delivery_channels()
        channel_list = channels.get("DeliveryChannels", [])
    except ClientError:
        channel_list = []

    for channel in channel_list:
        channel_name = channel["name"]
        if dry_run:
            info(f"[DRY-RUN] Would delete delivery channel: " f"{channel_name}")
        else:
            try:
                config_client.delete_delivery_channel(DeliveryChannelName=channel_name)
                success(f"Deleted delivery channel: {channel_name}")
            except ClientError as e:
                error(f"Failed to delete delivery channel: {e}")

    # Delete Config rules
    try:
        paginator = config_client.get_paginator("describe_config_rules")
        for page in paginator.paginate():
            for rule in page.get("ConfigRules", []):
                rule_name = rule["ConfigRuleName"]
                if dry_run:
                    info(f"[DRY-RUN] Would delete Config rule: " f"{rule_name}")
                else:
                    try:
                        config_client.delete_config_rule(ConfigRuleName=rule_name)
                        success(f"Deleted Config rule: {rule_name}")
                    except ClientError as e:
                        error(f"Failed to delete Config rule " f"{rule_name}: {e}")
    except ClientError as e:
        warn(f"Could not list Config rules: {e}")


def cleanup_cloudwatch_logs(logs_client, dry_run: bool = True) -> int:
    """Set all aura DEV log groups to 1-day retention.

    Log groups from deleted stacks retain stored data indefinitely unless
    retention is set. Setting retention to 1 day causes AWS to purge stored
    data within 24 hours, eliminating log storage charges.

    Does NOT delete log groups (preserves ability to diagnose recent issues).
    Returns count of log groups updated.
    """
    count = 0
    prefixes = ["/aura/", "/aws/"]

    for prefix in prefixes:
        paginator = logs_client.get_paginator("describe_log_groups")
        for page in paginator.paginate(logGroupNamePrefix=prefix):
            for group in page.get("logGroups", []):
                group_name = group["logGroupName"]
                # Only target aura-related log groups
                if "aura" not in group_name.lower():
                    continue
                current_retention = group.get("retentionInDays")
                if current_retention is not None and current_retention <= 1:
                    continue  # Already at 1 day or less

                if dry_run:
                    info(
                        f"[DRY-RUN] Would set 1-day retention on: "
                        f"{group_name} (current: "
                        f"{current_retention or 'never expires'})"
                    )
                else:
                    try:
                        logs_client.put_retention_policy(
                            logGroupName=group_name, retentionInDays=1
                        )
                        success(f"Set 1-day retention on: {group_name}")
                    except ClientError as e:
                        error(f"Failed to set retention on " f"{group_name}: {e}")
                count += 1

    if count == 0:
        info("All aura log groups already have 1-day retention (or none found)")
    return count


def schedule_kms_key_deletion(kms_client, cfn_client, dry_run: bool = True) -> int:
    """Schedule deletion of all KMS CMKs in the aura-kms-dev stack.

    The aura-kms-dev protected stack (DeletionPolicy: Retain) keeps 4 CMKs
    alive indefinitely. This function schedules them for deletion with a
    7-day pending window (the minimum allowed by KMS).

    WARNING: This is irreversible. Any data encrypted with these keys
    (old Neptune cluster snapshots, S3 objects using CMK encryption) becomes
    permanently unrecoverable after the deletion window.

    NOTE: Restore is NOT affected. The restore templates (neptune-simplified.yaml,
    opensearch.yaml) use AWS-managed encryption, not these CMKs. Neptune restores
    as a fresh empty cluster regardless. Old CMK-encrypted snapshots can be
    deleted since restore never uses them.

    Returns count of keys scheduled.
    """
    # Get KMS key IDs from aura-kms-dev stack outputs
    try:
        resp = cfn_client.describe_stacks(StackName=KMS_STACK_NAME)
        stacks = resp.get("Stacks", [])
    except ClientError as e:
        warn(f"KMS stack '{KMS_STACK_NAME}' not found: {e}")
        return 0

    if not stacks:
        warn(f"KMS stack '{KMS_STACK_NAME}' not found")
        return 0

    outputs = stacks[0].get("Outputs", [])
    key_ids = []
    for output in outputs:
        output_key = output.get("OutputKey", "")
        output_value = output.get("OutputValue", "")
        # KMS key outputs typically contain "Key" in the name and
        # the value is a key ID or ARN
        if "Key" in output_key and output_value:
            # Extract key ID from ARN if necessary
            if output_value.startswith("arn:"):
                parts = output_value.split("/")
                if len(parts) >= 2:
                    key_ids.append(parts[-1])
            else:
                key_ids.append(output_value)

    if not key_ids:
        info("No KMS key IDs found in stack outputs")
        return 0

    count = 0
    for key_id in key_ids:
        try:
            key_meta = kms_client.describe_key(KeyId=key_id)
            key_state = key_meta["KeyMetadata"]["KeyState"]
        except ClientError as e:
            warn(f"Could not describe key {key_id}: {e}")
            continue

        if key_state == "PendingDeletion":
            info(f"Key {key_id} already pending deletion - skipping")
            continue

        if key_state != "Enabled" and key_state != "Disabled":
            warn(f"Key {key_id} in unexpected state '{key_state}' - " f"skipping")
            continue

        if dry_run:
            info(
                f"[DRY-RUN] Would schedule deletion of KMS key: "
                f"{key_id} (state: {key_state})"
            )
        else:
            try:
                kms_client.schedule_key_deletion(KeyId=key_id, PendingWindowInDays=7)
                success(
                    f"Scheduled KMS key {key_id} for deletion "
                    f"(7-day pending window)"
                )
            except ClientError as e:
                error(f"Failed to schedule deletion for key " f"{key_id}: {e}")
        count += 1

    return count


def do_cleanup(args: argparse.Namespace) -> int:
    """Execute post-shutdown cost cleanup for the DEV environment.

    Targets costs that persist after the kill-switch shutdown:
      - Orphaned ELBs from Kubernetes
      - AWS Config recorder + rules
      - CloudWatch log group storage
      - KMS CMKs (--schedule-kms-deletion only, IRREVERSIBLE)
    """
    dry_run = not args.execute
    region = args.region

    session = boto3.Session(region_name=region)
    sts = session.client("sts")
    codebuild = session.client("codebuild")
    elbv2 = session.client("elbv2")
    elb = session.client("elb")
    config = session.client("config")
    logs = session.client("logs")
    kms = session.client("kms")
    cfn = session.client("cloudformation")

    if dry_run:
        info(
            f"{BOLD}=== DRY-RUN MODE "
            f"(use --execute to perform real operations) ==={NC}\n"
        )

    # Pre-flight
    phase_header(0, "Pre-flight Checks")
    pre_flight_checks(sts, codebuild, region)

    # Confirmation prompt
    if args.execute and not args.force:
        print(
            f"\n{YELLOW}{BOLD}WARNING: This will clean up residual "
            f"DEV resources to save estimated monthly.{NC}"
        )
        if getattr(args, "schedule_kms_deletion", False):
            print(
                f"\n  {RED}{BOLD}KMS KEY DELETION IS ENABLED. "
                f"This is IRREVERSIBLE.{NC}"
            )
            print(
                f"  {RED}Old CMK-encrypted Neptune snapshots become "
                f"unrecoverable after the 7-day window.{NC}"
            )
            print(
                f"  {GREEN}Restore is NOT affected — neptune-simplified.yaml "
                f"deploys fresh with AWS-managed encryption.{NC}"
            )
            print(
                f"  {YELLOW}Delete old Neptune snapshots manually after "
                f"key deletion completes.{NC}\n"
            )
        confirm = input(f"  Type '{YELLOW}CLEANUP DEV{NC}' to confirm: ")
        if confirm.strip() != "CLEANUP DEV":
            error("Confirmation failed - aborting")
            return 1

    total_savings = 0
    errors_occurred = False

    # Step 1: Orphaned ELBs
    phase_header(1, "Orphaned Load Balancers")
    try:
        elb_count = cleanup_orphaned_elbs(elbv2, elb, dry_run=dry_run)
        if elb_count > 0:
            total_savings += 29
            info(f"Found {elb_count} orphaned load balancer(s)")
    except Exception as e:
        error(f"ELB cleanup failed: {e}")
        errors_occurred = True

    # Step 2: AWS Config
    phase_header(2, "AWS Config Recorder + Rules")
    try:
        cleanup_config_recorder(config, dry_run=dry_run)
        total_savings += 60
    except Exception as e:
        error(f"Config cleanup failed: {e}")
        errors_occurred = True

    # Step 3: CloudWatch Logs
    phase_header(3, "CloudWatch Log Group Retention")
    try:
        log_count = cleanup_cloudwatch_logs(logs, dry_run=dry_run)
        if log_count > 0:
            total_savings += 58
            info(f"Updated retention for {log_count} log group(s)")
    except Exception as e:
        error(f"CloudWatch Logs cleanup failed: {e}")
        errors_occurred = True

    # Step 4: KMS Keys (only if --schedule-kms-deletion is set)
    phase_header(4, "KMS Customer-Managed Keys")
    if getattr(args, "schedule_kms_deletion", False):
        try:
            kms_count = schedule_kms_key_deletion(kms, cfn, dry_run=dry_run)
            if kms_count > 0:
                total_savings += 20
                info(f"Processed {kms_count} KMS key(s)")
        except Exception as e:
            error(f"KMS cleanup failed: {e}")
            errors_occurred = True
    else:
        info("Skipping KMS key deletion (use --schedule-kms-deletion " "to enable)")
        info(
            f"{YELLOW}NOTE: KMS deletion is irreversible but restore is "
            f"unaffected (fresh Neptune cluster, AWS-managed encryption).{NC}"
        )

    # Summary
    print(f"\n{BOLD}{'=' * 60}{NC}")
    action = "Estimated" if dry_run else "Actual"
    print(f"{BOLD}{action} monthly savings: " f"~${total_savings}/month{NC}")
    if dry_run:
        print(f"\n{YELLOW}Run with --execute to apply these changes.{NC}")
    print()

    return 1 if errors_occurred else 0


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DEV Environment Kill-Switch for Project Aura",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s shutdown                  # Dry-run: show what would be deleted
  %(prog)s shutdown --execute        # Actually delete DEV stacks (significant monthly savings/mo savings)
  %(prog)s restore --execute         # Redeploy core infra + trigger CodeBuild (~90-120 min)
  %(prog)s status                    # Show current DEV environment state
  %(prog)s cleanup                   # Dry-run: show orphaned ELBs, Config, logs, KMS keys
  %(prog)s cleanup --execute         # Delete ELBs, stop Config, purge log retention
  %(prog)s cleanup --execute --schedule-kms-deletion  # Also schedule KMS deletion (IRREVERSIBLE)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.required = True

    for name in ["shutdown", "restore", "status", "cleanup"]:
        sub = subparsers.add_parser(name)
        sub.add_argument(
            "--region",
            default=DEFAULT_REGION,
            help=f"AWS region (default: {DEFAULT_REGION})",
        )
        sub.add_argument("--verbose", action="store_true", help="Enable debug logging")
        if name not in ("status",):
            sub.add_argument(
                "--execute",
                action="store_true",
                help="Perform real operations (default is dry-run)",
            )
            sub.add_argument(
                "--force",
                action="store_true",
                help="Skip interactive confirmation prompt",
            )
        if name == "shutdown":
            sub.add_argument(
                "--skip-snapshot",
                action="store_true",
                help="Skip Neptune snapshot creation",
            )
        if name == "cleanup":
            sub.add_argument(
                "--schedule-kms-deletion",
                action="store_true",
                help="Schedule KMS CMK deletion (IRREVERSIBLE)",
            )

    args = parser.parse_args()

    global log
    log = _setup_logging(verbose=getattr(args, "verbose", False))

    print(f"\n{BOLD}Project Aura - DEV Kill-Switch{NC}")
    print(f"Environment: {ENVIRONMENT} (hardcoded)")
    print(f"Region: {args.region}")
    print(f"Command: {args.command}")
    if hasattr(args, "execute"):
        print(f"Mode: {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print(f"Stacks managed: {len(STACK_DEFINITIONS)}")
    print(f"Protected stacks: {len(PROTECTED_STACKS)}")
    print()

    if args.command == "shutdown":
        return do_shutdown(args)
    elif args.command == "restore":
        return do_restore(args)
    elif args.command == "status":
        return do_status(args)
    elif args.command == "cleanup":
        return do_cleanup(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
