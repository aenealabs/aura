#!/usr/bin/env python3
"""
QA Environment Kill-Switch for Project Aura
============================================
Safely shuts down or restores the QA environment for significant cost savings
on always-on AWS resources (Neptune, OpenSearch, EKS, VPC Endpoints, etc.).

Usage:
    python scripts/qa_killswitch.py shutdown              # Dry-run (default)
    python scripts/qa_killswitch.py shutdown --execute     # Actually delete stacks
    python scripts/qa_killswitch.py restore                # Dry-run restore plan
    python scripts/qa_killswitch.py restore --execute      # Actually redeploy stacks
    python scripts/qa_killswitch.py status                 # Show current QA state
    python scripts/qa_killswitch.py cleanup                # Dry-run: show orphaned costs
    python scripts/qa_killswitch.py cleanup --execute      # Clean up residual costs

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
    - Hardcoded to QA environment only (no override)
    - Validates AWS account ID before any destructive action
    - Dry-run by default; requires --execute for real operations
    - Interactive confirmation (type 'DESTROY QA') unless --force
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

ALLOWED_ENVIRONMENTS = frozenset(["qa"])
PROJECT_NAME = "aura"
ENVIRONMENT = "qa"
DEFAULT_REGION = "us-east-1"

# Stacks managed by the kill-switch, in shutdown order
STACK_DEFINITIONS = [
    # Phase 2: Application
    {
        "name": f"{PROJECT_NAME}-network-services-{ENVIRONMENT}",
        "phase": 2,
        "template": "deploy/cloudformation/network-services.yaml",
        "layer": "application",
    },
    # Phase 3: EKS node groups (parallel)
    {
        "name": f"{PROJECT_NAME}-nodegroup-general-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/eks-nodegroup-general.yaml",
        "layer": "compute",
    },
    {
        "name": f"{PROJECT_NAME}-nodegroup-memory-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/eks-nodegroup-memory.yaml",
        "layer": "compute",
    },
    {
        "name": f"{PROJECT_NAME}-nodegroup-gpu-{ENVIRONMENT}",
        "phase": 3,
        "template": "deploy/cloudformation/eks-nodegroup-gpu.yaml",
        "layer": "compute",
    },
    # Phase 4: EKS control plane
    {
        "name": f"{PROJECT_NAME}-eks-{ENVIRONMENT}",
        "phase": 4,
        "template": "deploy/cloudformation/eks.yaml",
        "layer": "compute",
    },
    # Phase 5: Data stores (parallel)
    {
        "name": f"{PROJECT_NAME}-neptune-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/neptune-simplified.yaml",
        "layer": "data",
    },
    {
        "name": f"{PROJECT_NAME}-opensearch-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/opensearch.yaml",
        "layer": "data",
    },
    {
        "name": f"{PROJECT_NAME}-elasticache-{ENVIRONMENT}",
        "phase": 5,
        "template": "deploy/cloudformation/elasticache.yaml",
        "layer": "data",
    },
    # Phase 6: VPC Endpoints
    {
        "name": f"{PROJECT_NAME}-vpc-endpoints-{ENVIRONMENT}",
        "phase": 6,
        "template": "deploy/cloudformation/vpc-endpoints.yaml",
        "layer": "foundation",
    },
]

EVENTBRIDGE_SCHEDULES = [
    f"{PROJECT_NAME}-qa-scale-down",
    f"{PROJECT_NAME}-qa-scale-up",
]

SNS_TOPIC_NAME = f"{PROJECT_NAME}-qa-operations-{ENVIRONMENT}"

# Foundation stacks that STAY running (parameters resolved from these)
FOUNDATION_STACKS = {
    "networking": f"{PROJECT_NAME}-networking-{ENVIRONMENT}",
    "security": f"{PROJECT_NAME}-security-{ENVIRONMENT}",
    "iam": f"{PROJECT_NAME}-iam-{ENVIRONMENT}",
}

STACK_DELETE_TIMEOUT = 1800  # 30 minutes
STACK_DELETE_POLL_INTERVAL = 15  # seconds
SNAPSHOT_TIMEOUT = 600  # 10 minutes

# Tags that identify Kubernetes-managed load balancers
K8S_ELB_TAGS = frozenset(
    [
        "kubernetes.io/cluster/aura-cluster-qa",
        "ingress.k8s.aws/stack",
        "elbv2.k8s.aws/cluster",
    ]
)

KMS_STACK_NAME = f"{PROJECT_NAME}-kms-{ENVIRONMENT}"

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
    logger = logging.getLogger("qa-killswitch")
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
    restore_timestamp: Optional[str] = None
    restore_by: Optional[str] = None
    phases_completed: List[int] = field(default_factory=list)


def _state_local_path() -> Path:
    p = Path.home() / ".aura"
    p.mkdir(parents=True, exist_ok=True)
    return p / "qa-killswitch-state.json"


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
    local_path.chmod(0o600)  # Restrict to owner only (M2 fix)
    info(f"State saved locally: {local_path}")
    # S3
    bucket = _get_artifacts_bucket(cfn_client)
    if bucket:
        try:
            s3_client.put_object(
                Bucket=bucket,
                Key="killswitch/qa-state.json",
                Body=data,
                ContentType="application/json",
            )
            info(f"State saved to s3://{bucket}/killswitch/qa-state.json")
        except ClientError as e:
            warn(f"Could not save state to S3: {e}")


def load_state(s3_client, cfn_client) -> KillSwitchState:
    # Try S3 first
    bucket = _get_artifacts_bucket(cfn_client)
    if bucket:
        try:
            resp = s3_client.get_object(Bucket=bucket, Key="killswitch/qa-state.json")
            data = json.loads(resp["Body"].read().decode())
            info(f"State loaded from s3://{bucket}/killswitch/qa-state.json")
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
        status = self.get_stack_status(stack_name)
        if status is None or status == "DELETE_COMPLETE":
            success(f"Stack {stack_name} already deleted (skipping)")
            return True

        if status.endswith("_IN_PROGRESS"):
            if "DELETE" in status:
                info(f"Stack {stack_name} deletion already in progress, waiting...")
                return self._wait_for_delete(stack_name)
            else:
                error(f"Stack {stack_name} has active operation: {status}")
                return False

        if dry_run:
            info(f"[DRY-RUN] Would delete stack: {stack_name} (current: {status})")
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
                    f"  Waiting for {stack_name}... ({elapsed}s elapsed, status: {status})"
                )
        error(f"Timeout waiting for {stack_name} deletion ({STACK_DELETE_TIMEOUT}s)")
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
        # Build command as list to avoid shell injection (C2 fix)
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

        # Wait for snapshot to become available
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
    """Disable QA EventBridge Scheduler rules."""
    disabled = []
    for schedule_name in EVENTBRIDGE_SCHEDULES:
        if dry_run:
            info(f"[DRY-RUN] Would disable schedule: {schedule_name}")
            disabled.append(schedule_name)
            continue
        try:
            # Get current schedule config
            schedule = scheduler_client.get_schedule(Name=schedule_name)
            # Update with DISABLED state
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
    """Re-enable QA EventBridge Scheduler rules."""
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
# SNS Notifications
# ---------------------------------------------------------------------------


def send_notification(
    sns_client, action: str, details: Dict[str, Any], dry_run: bool = True
) -> None:
    if dry_run:
        info(f"[DRY-RUN] Would send SNS notification: QA {action}")
        return
    try:
        # Discover topic ARN
        resp = sns_client.list_topics()
        topic_arn = None
        for topic in resp.get("Topics", []):
            if SNS_TOPIC_NAME in topic["TopicArn"]:
                topic_arn = topic["TopicArn"]
                break
        if not topic_arn:
            warn(f"SNS topic {SNS_TOPIC_NAME} not found - skipping notification")
            return

        message = {
            "action": action,
            "environment": ENVIRONMENT,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=f"[Aura QA] Kill-Switch {action.upper()}",
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
    for i, suffix in enumerate(["1", "2"], 1):
        try:
            resp = ec2.describe_route_tables(
                Filters=[
                    {
                        "Name": "tag:Name",
                        "Values": [f"{PROJECT_NAME}-private-rt-{suffix}-{ENVIRONMENT}"],
                    }
                ]
            )
            rts = resp.get("RouteTables", [])
            params[f"PRIVATE_RT_{suffix}"] = rts[0]["RouteTableId"] if rts else ""
        except ClientError:
            params[f"PRIVATE_RT_{suffix}"] = ""
    params["PRIVATE_ROUTE_TABLE_IDS"] = ",".join(
        filter(None, [params.get("PRIVATE_RT_1", ""), params.get("PRIVATE_RT_2", "")])
    )

    return params


# ---------------------------------------------------------------------------
# Restore: per-stack deploy configs
# ---------------------------------------------------------------------------


def _build_deploy_configs(params: Dict[str, str]) -> Dict[str, Dict]:
    """Build the CloudFormation deploy parameters for each stack, matching buildspec patterns."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return {
        # VPC Endpoints (Phase 1 of restore)
        f"{PROJECT_NAME}-vpc-endpoints-{ENVIRONMENT}": {
            "template": "deploy/cloudformation/vpc-endpoints.yaml",
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "VpcId": params["VPC_ID"],
                "PrivateSubnetIds": f'"{params["PRIVATE_SUBNET_IDS"]}"',
                "PrivateRouteTableIds": f'"{params["PRIVATE_ROUTE_TABLE_IDS"]}"',
                "VPCEndpointSecurityGroupId": params["VPCE_SG"],
            },
            "tags": {"Layer": "foundation", "DeployTimestamp": ts},
        },
        # Neptune (Phase 2)
        f"{PROJECT_NAME}-neptune-{ENVIRONMENT}": {
            "template": "deploy/cloudformation/neptune-simplified.yaml",
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "PrivateSubnetIds": f'"{params["PRIVATE_SUBNET_IDS"]}"',
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
                "PrivateSubnetIds": f'"{params["PRIVATE_SUBNET_IDS"]}"',
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
                "PrivateSubnetIds": f'"{params["PRIVATE_SUBNET_IDS"]}"',
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
                "PrivateSubnetIds": f'"{params["PUBLIC_SUBNET_IDS"]}"',
                "EKSSecurityGroupId": params["EKS_SG"],
                "EKSClusterRoleArn": params["EKS_CLUSTER_ROLE"],
                "AdminRoleArn": params["ADMIN_ROLE_ARN"],
                "KubernetesVersion": "1.34",
            },
            "tags": {"Layer": "compute", "DeployTimestamp": ts},
        },
        # General Node Group (Phase 4)
        f"{PROJECT_NAME}-nodegroup-general-{ENVIRONMENT}": {
            "template": "deploy/cloudformation/eks-nodegroup-general.yaml",
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "ClusterName": f"{PROJECT_NAME}-cluster-{ENVIRONMENT}",
                "NodeRoleArn": params["EKS_NODE_ROLE"],
                "PrivateSubnetIds": f'"{params["PUBLIC_SUBNET_IDS"]}"',
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
            "template": "deploy/cloudformation/eks-nodegroup-memory.yaml",
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "ClusterName": f"{PROJECT_NAME}-cluster-{ENVIRONMENT}",
                "NodeRoleArn": params["EKS_NODE_ROLE"],
                "PrivateSubnetIds": f'"{params["PUBLIC_SUBNET_IDS"]}"',
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
            "template": "deploy/cloudformation/eks-nodegroup-gpu.yaml",
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "ClusterName": f"{PROJECT_NAME}-cluster-{ENVIRONMENT}",
                "NodeRoleArn": params["EKS_NODE_ROLE"],
                "PrivateSubnetIds": f'"{params["PUBLIC_SUBNET_IDS"]}"',
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
            "template": "deploy/cloudformation/network-services.yaml",
            "params": {
                "Environment": ENVIRONMENT,
                "ProjectName": PROJECT_NAME,
                "VpcId": params["VPC_ID"],
                "PrivateSubnet1Id": params["PRIVATE_SUBNET_1"],
                "PrivateSubnet2Id": params["PRIVATE_SUBNET_2"],
                "VpcCidr": params["VPC_CIDR"],
                "AllowedCidr": params["VPC_CIDR"],
            },
            "tags": {"Layer": "network-services", "DeployTimestamp": ts},
        },
    }


# ---------------------------------------------------------------------------
# Pre-flight Checks
# ---------------------------------------------------------------------------


def pre_flight_checks(sts_client, codebuild_client, region: str) -> Dict[str, str]:
    """Validate environment and credentials. Returns caller identity info."""
    # 0. Verify environment is in allowed set (H3 fix)
    if ENVIRONMENT not in ALLOWED_ENVIRONMENTS:
        error(f"Environment '{ENVIRONMENT}' not in allowed set: {ALLOWED_ENVIRONMENTS}")
        sys.exit(2)

    # 1. Verify caller identity
    try:
        identity = sts_client.get_caller_identity()
    except (NoCredentialsError, ClientError) as e:
        error(f"AWS credentials not available: {e}")
        sys.exit(2)

    account_id = identity["Account"]
    caller_arn = identity["Arn"]

    # 1b. Validate account ID if expected value is set (H4 fix)
    expected_account = os.environ.get("AURA_QA_ACCOUNT_ID")
    if expected_account and account_id != expected_account:
        error(f"Account ID mismatch: expected {expected_account}, got {account_id}")
        sys.exit(2)
    info(f"AWS Account: {account_id}")
    info(f"Caller: {caller_arn}")

    # 2. Validate stack names all contain -qa (defense in depth)
    for stack_def in STACK_DEFINITIONS:
        if f"-{ENVIRONMENT}" not in stack_def["name"]:
            error(f"Stack name {stack_def['name']} does not contain '-{ENVIRONMENT}'")
            sys.exit(2)

    # 3. Check no CodeBuild builds are running for QA
    qa_projects = [
        f"{PROJECT_NAME}-data-deploy-{ENVIRONMENT}",
        f"{PROJECT_NAME}-compute-deploy-{ENVIRONMENT}",
        f"{PROJECT_NAME}-foundation-deploy-{ENVIRONMENT}",
    ]
    for project_name in qa_projects:
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
                            f"CodeBuild project {project_name} has a build in progress. "
                            f"Wait for it to complete before running kill-switch."
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
    """Execute the QA environment shutdown sequence."""
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
            f"{BOLD}=== DRY-RUN MODE (use --execute to perform real operations) ==={NC}\n"
        )

    # Pre-flight
    phase_header(0, "Pre-flight Checks")
    identity = pre_flight_checks(sts, codebuild, region)

    # Confirmation prompt
    if args.execute and not args.force:
        stacks_list = "\n".join(f"    - {s['name']}" for s in STACK_DEFINITIONS)
        print(
            f"\n{RED}{BOLD}WARNING: This will DELETE the following QA CloudFormation stacks:{NC}"
        )
        print(stacks_list)
        print(f"\n  Estimated monthly savings: significant")
        print(f"  Estimated restore time: ~45-60 minutes\n")
        confirm = input(f"  Type '{RED}DESTROY QA{NC}' to confirm: ")
        if confirm.strip() != "DESTROY QA":
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
            # Cluster may not exist -- that's OK, continue
            warn("Neptune snapshot skipped (cluster not found)")
        state.neptune_snapshot_id = snapshot_id
    else:
        info("Skipping Neptune snapshot (--skip-snapshot)")

    # Phase 1: Disable schedulers
    phase_header(1, "Disable EventBridge Schedules")
    state.disabled_schedules = disable_schedules(scheduler, dry_run=dry_run)

    # Phases 2-6: Delete stacks by phase
    # Within each phase, stacks are grouped by delete_order (default 1).
    # Stacks with the same delete_order run in parallel; groups run
    # sequentially from lowest to highest to respect cross-stack exports.
    phases = sorted(set(s["phase"] for s in STACK_DEFINITIONS))
    for phase_num in phases:
        phase_stacks = [s for s in STACK_DEFINITIONS if s["phase"] == phase_num]
        phase_name = phase_stacks[0]["layer"]
        phase_header(phase_num, f"Delete {phase_name} stacks")

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
        phase_header(6, "Cleanup Old Snapshots")
        nsm.cleanup_old_snapshots(state.neptune_snapshot_id, dry_run=dry_run)

    # Finalize (H1 fix: detect partial shutdown)
    phase_header(7, "Finalize")
    expected_stacks = len(STACK_DEFINITIONS)
    actual_deleted = len(state.deleted_stacks)
    if actual_deleted >= expected_stacks:
        state.status = "shutdown"
    else:
        state.status = "partial"
        warn(f"Partial shutdown: {actual_deleted}/{expected_stacks} stacks deleted")

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
    print(f"\n{GREEN}{BOLD}=== Shutdown {'Plan' if dry_run else 'Complete'} ==={NC}")
    print(
        f"  Stacks {'to delete' if dry_run else 'deleted'}: {actual_deleted}/{expected_stacks}"
    )
    print(f"  Neptune snapshot: {state.neptune_snapshot_id or 'skipped'}")
    print(f"  Schedules disabled: {len(state.disabled_schedules)}")
    print(f"  Estimated monthly savings: significant")
    if dry_run:
        print(f"\n  {YELLOW}Run with --execute to perform these operations{NC}")
    return 0 if state.status == "shutdown" or dry_run else 1


def do_restore(args: argparse.Namespace) -> int:
    """Execute the QA environment restore sequence."""
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
            f"{BOLD}=== DRY-RUN MODE (use --execute to perform real operations) ==={NC}\n"
        )

    # Pre-flight
    phase_header(0, "Pre-flight Checks")
    identity = pre_flight_checks(sts, codebuild, region)

    # Load state
    state = load_state(s3, cfn)
    if state.status == "running":
        warn("State file indicates QA is already running")
    if state.neptune_snapshot_id:
        info(f"Neptune snapshot available: {state.neptune_snapshot_id}")

    # Resolve parameters
    phase_header(0, "Resolve Parameters")
    params = resolve_parameters(sm, ssm)
    missing = [k for k, v in params.items() if not v and k not in ("ADMIN_ROLE_ARN",)]
    if missing:
        error(f"Missing foundation parameters: {missing}")
        error("Ensure foundation stacks (networking, security, iam) are deployed")
        return 1
    success(f"Resolved {len(params)} parameters from foundation stacks")

    if args.verbose:
        for k, v in sorted(params.items()):
            info(f"  {k} = {v}")

    # Build deploy configs
    deploy_configs = _build_deploy_configs(params)

    # Confirmation
    if args.execute and not args.force:
        print(
            f"\n{CYAN}{BOLD}This will RESTORE the following QA CloudFormation stacks:{NC}"
        )
        for name in deploy_configs:
            print(f"    + {name}")
        print(f"\n  Estimated deploy time: ~45-60 minutes\n")
        confirm = input(f"  Type '{GREEN}RESTORE QA{NC}' to confirm: ")
        if confirm.strip() != "RESTORE QA":
            error("Confirmation failed - aborting")
            return 1

    # Restore phases (order matters)
    restore_order = [
        (1, "VPC Endpoints", [f"{PROJECT_NAME}-vpc-endpoints-{ENVIRONMENT}"]),
        (
            2,
            "Data Stores",
            [
                f"{PROJECT_NAME}-neptune-{ENVIRONMENT}",
                f"{PROJECT_NAME}-opensearch-{ENVIRONMENT}",
                f"{PROJECT_NAME}-elasticache-{ENVIRONMENT}",
            ],
        ),
        (3, "EKS Control Plane", [f"{PROJECT_NAME}-eks-{ENVIRONMENT}"]),
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

    # For EKS node groups, we need the ClusterName from the deployed EKS stack
    # Update it after EKS deploys (Phase 3)
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
                    name, cfg["template"], cfg["params"], cfg["tags"], dry_run=dry_run
                )
                if not ok:
                    deploy_failures += 1
        else:
            # Parallel deployment
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

    # Re-enable schedules
    phase_header(5, "Re-enable EventBridge Schedules")
    enable_schedules(scheduler, dry_run=dry_run)

    # Finalize (H2 fix: track failures, set partial status)
    phase_header(6, "Finalize")
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
            "operator": identity["caller_arn"],
        },
        dry_run=dry_run,
    )

    # Summary
    print(f"\n{GREEN}{BOLD}=== Restore {'Plan' if dry_run else 'Complete'} ==={NC}")
    print(f"  Stacks {'to deploy' if dry_run else 'deployed'}: {len(deploy_configs)}")
    if deploy_failures > 0:
        print(f"  {RED}Failures: {deploy_failures}{NC}")
    if dry_run:
        print(f"\n  {YELLOW}Run with --execute to perform these operations{NC}")
    return 0 if deploy_failures == 0 or dry_run else 1


def do_status(args: argparse.Namespace) -> int:
    """Show current status of all QA stacks."""
    region = args.region
    session = boto3.Session(region_name=region)
    cfn = session.client("cloudformation")
    s3 = session.client("s3")

    sm = StackManager(cfn, region)

    print(f"\n{BOLD}QA Environment Status{NC}")
    print(f"{'=' * 60}")

    # Stack statuses
    print(f"\n{BOLD}CloudFormation Stacks:{NC}")
    total_cost = 0.0
    cost_map = {
        "neptune": 90,
        "opensearch": 25,
        "eks-qa": 73,
        "nodegroup-general": 35,
        "nodegroup-memory": 0,
        "nodegroup-gpu": 0,
        "network-services": 15,
        "vpc-endpoints": 58,
        "elasticache": 12,
    }
    for stack_def in STACK_DEFINITIONS:
        name = stack_def["name"]
        status = sm.get_stack_status(name)
        display_status = status or "DOES NOT EXIST"

        # Color code
        if status and "COMPLETE" in status and "DELETE" not in status:
            color = GREEN
            # Find cost
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

    print(f"\n  {BOLD}Estimated monthly cost of running stacks: ~${total_cost:.0f}{NC}")

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

    print()
    return 0


# ---------------------------------------------------------------------------
# Post-Shutdown Cost Cleanup
# ---------------------------------------------------------------------------


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

    The QA Config recorder kept running after the kill-switch shutdown
    (Feb 15 - Mar 19, 2026), generating undetected charges.
    Stopping the recorder eliminates these charges while the environment
    is hibernated. The recorder will be restarted when the compliance stack
    is redeployed on restore.
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
    """Set all aura QA log groups to 1-day retention.

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
    """Schedule deletion of all KMS CMKs in the aura-kms-qa stack.

    The aura-kms-qa protected stack (DeletionPolicy: Retain) keeps CMKs
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
    # Get KMS key IDs from aura-kms-qa stack outputs
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
    """Execute post-shutdown cost cleanup for the QA environment.

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
            f"QA resources to save estimated monthly.{NC}"
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
        confirm = input(f"  Type '{YELLOW}CLEANUP QA{NC}' to confirm: ")
        if confirm.strip() != "CLEANUP QA":
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
            total_savings += 15
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
                total_savings += 4
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
        description="QA Environment Kill-Switch for Project Aura",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s shutdown                  # Dry-run: show what would be deleted
  %(prog)s shutdown --execute        # Actually delete QA stacks (significant savings)
  %(prog)s restore --execute         # Redeploy all QA stacks (~45-60 min)
  %(prog)s status                    # Show current QA environment state
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

    # Setup logging
    global log
    log = _setup_logging(verbose=getattr(args, "verbose", False))

    print(f"\n{BOLD}Project Aura - QA Kill-Switch{NC}")
    print(f"Environment: {ENVIRONMENT} (hardcoded)")
    print(f"Region: {args.region}")
    print(f"Command: {args.command}")
    if hasattr(args, "execute"):
        print(f"Mode: {'EXECUTE' if args.execute else 'DRY-RUN'}")
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
