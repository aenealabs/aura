#!/usr/bin/env python3
"""
Project Aura - Code Staging Script for Sandbox Testing

Stages code from a Git repository to S3 for HITL sandbox testing.
This enables ECS Fargate tasks in private subnets (no NAT Gateway)
to access code via S3 VPC endpoint.

Usage:
    # Stage code and get S3 URI
    ./stage-code-for-sandbox.py --repo https://github.com/org/repo --branch main --patch-id PATCH-001

    # Stage and trigger workflow
    ./stage-code-for-sandbox.py --repo https://github.com/org/repo --patch-id PATCH-001 --trigger

Environment Variables:
    AWS_PROFILE     - AWS profile to use (default: aura-admin)
    ENVIRONMENT     - Target environment (default: dev)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import boto3


def get_aws_account_id() -> str:
    """Get current AWS account ID."""
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


def get_bucket_name(environment: str) -> str:
    """Get the sandbox artifacts bucket name."""
    account_id = get_aws_account_id()
    return f"aura-sandbox-artifacts-{account_id}-{environment}"


def clone_repository(repo_url: str, branch: str, target_dir: Path) -> str:
    """Clone repository and return commit hash."""
    print(f"Cloning {repo_url} (branch: {branch})...")

    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(target_dir)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Error cloning repository: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Get commit hash
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(target_dir),
        capture_output=True,
        text=True,
    )

    commit_hash = result.stdout.strip()
    print(f"Cloned successfully. Commit: {commit_hash}")
    return commit_hash


def create_tarball(source_dir: Path, output_path: Path) -> int:
    """Create gzipped tarball of source directory. Returns size in bytes."""
    print(f"Creating tarball...")

    with tarfile.open(output_path, "w:gz") as tar:
        # Add all files from source directory
        for item in source_dir.iterdir():
            tar.add(item, arcname=item.name)

    size = output_path.stat().st_size
    print(f"Tarball created: {size / 1024 / 1024:.2f} MB")
    return size


def upload_to_s3(local_path: Path, bucket: str, key: str) -> str:
    """Upload file to S3 and return S3 URI."""
    print(f"Uploading to s3://{bucket}/{key}...")

    s3 = boto3.client("s3")
    s3.upload_file(
        str(local_path),
        bucket,
        key,
        ExtraArgs={
            "ServerSideEncryption": "AES256",
            "Metadata": {
                "staged-by": "stage-code-for-sandbox",
                "staged-at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        },
    )

    s3_uri = f"s3://{bucket}/{key}"
    print(f"Uploaded successfully: {s3_uri}")
    return s3_uri


def trigger_workflow(
    code_source: str,
    code_bucket: str,
    code_key: str,
    patch_id: str,
    test_suite: str,
    severity: str,
    vulnerability_id: str,
    environment: str,
) -> str:
    """Trigger the HITL patch workflow and return execution ARN."""
    print(f"Triggering HITL workflow...")

    sfn = boto3.client("stepfunctions")

    # Get workflow ARN
    state_machine_arn = f"arn:aws:states:{boto3.session.Session().region_name}:{get_aws_account_id()}:stateMachine:aura-hitl-patch-workflow-{environment}"

    # Get network configuration from CloudFormation exports
    cf = boto3.client("cloudformation")

    # Get security group
    try:
        exports = cf.list_exports()["Exports"]
        sg_export = next(
            (e for e in exports if e["Name"] == f"aura-ecs-workload-sg-{environment}"),
            None,
        )
        security_group_id = sg_export["Value"] if sg_export else None
    except Exception:
        security_group_id = None

    if not security_group_id:
        print(
            "Warning: Could not find ECS workload security group. Using sandbox SG.",
            file=sys.stderr,
        )
        # Fallback to sandbox security group
        sg_export = next(
            (e for e in exports if e["Name"] == f"aura-sandbox-sg-{environment}"),
            None,
        )
        security_group_id = sg_export["Value"] if sg_export else None

    # Get private subnet IDs from VPC
    ec2 = boto3.client("ec2")
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "tag:Project", "Values": ["aura"]}])[
        "Vpcs"
    ]

    if not vpcs:
        print("Error: Could not find Aura VPC", file=sys.stderr)
        sys.exit(1)

    vpc_id = vpcs[0]["VpcId"]

    subnets = ec2.describe_subnets(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "tag:Name", "Values": [f"*private*"]},
        ]
    )["Subnets"]

    subnet_ids = [s["SubnetId"] for s in subnets[:2]]  # Use first 2 private subnets

    if not subnet_ids:
        print("Error: Could not find private subnets", file=sys.stderr)
        sys.exit(1)

    # Build workflow input
    workflow_input = {
        "patch_id": patch_id,
        "code_source": code_source,
        "code_bucket": code_bucket,
        "code_key": code_key,
        "test_suite": test_suite,
        "severity": severity,
        "vulnerability_id": vulnerability_id,
        "branch": "main",
        "timeout_minutes": 30,
        "security_group_id": security_group_id,
        "subnet_ids": subnet_ids,
    }

    # Start execution
    execution_name = f"{patch_id}-{int(time.time())}"

    response = sfn.start_execution(
        stateMachineArn=state_machine_arn,
        name=execution_name,
        input=json.dumps(workflow_input),
    )

    execution_arn = response["executionArn"]
    print(f"Workflow started: {execution_arn}")
    print(f"Execution name: {execution_name}")

    return execution_arn


def main():
    parser = argparse.ArgumentParser(
        description="Stage code from Git to S3 for HITL sandbox testing"
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Git repository URL (e.g., https://github.com/org/repo)",
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Git branch to clone (default: main)",
    )
    parser.add_argument(
        "--patch-id",
        required=True,
        help="Unique patch identifier (e.g., PATCH-001)",
    )
    parser.add_argument(
        "--environment",
        default=os.environ.get("ENVIRONMENT", "dev"),
        help="Target environment (default: dev)",
    )
    parser.add_argument(
        "--trigger",
        action="store_true",
        help="Trigger the HITL workflow after staging",
    )
    parser.add_argument(
        "--test-suite",
        default="unit",
        choices=["unit", "integration", "security", "all"],
        help="Test suite to run (default: unit)",
    )
    parser.add_argument(
        "--severity",
        default="MEDIUM",
        choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        help="Patch severity (default: MEDIUM)",
    )
    parser.add_argument(
        "--vulnerability-id",
        default="",
        help="CVE or vulnerability ID (optional)",
    )
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Output result as JSON",
    )

    args = parser.parse_args()

    # Create temp directory for work
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        repo_dir = tmpdir / "repo"
        tarball_path = tmpdir / "code.tar.gz"

        # Clone repository
        commit_hash = clone_repository(args.repo, args.branch, repo_dir)

        # Create tarball
        tarball_size = create_tarball(repo_dir, tarball_path)

        # Upload to S3
        bucket = get_bucket_name(args.environment)
        timestamp = int(time.time())
        s3_key = f"code/{args.patch_id}/{timestamp}.tar.gz"

        s3_uri = upload_to_s3(tarball_path, bucket, s3_key)

        result = {
            "code_source": s3_uri,
            "patch_id": args.patch_id,
            "commit": commit_hash,
            "tarball_size_bytes": tarball_size,
            "bucket": bucket,
            "key": s3_key,
        }

        # Trigger workflow if requested
        if args.trigger:
            execution_arn = trigger_workflow(
                code_source=s3_uri,
                code_bucket=bucket,
                code_key=s3_key,
                patch_id=args.patch_id,
                test_suite=args.test_suite,
                severity=args.severity,
                vulnerability_id=args.vulnerability_id or f"VULN-{args.patch_id}",
                environment=args.environment,
            )
            result["execution_arn"] = execution_arn

        # Output result
        if args.output_json:
            print(json.dumps(result, indent=2))
        else:
            print("\n" + "=" * 50)
            print("CODE STAGING COMPLETE")
            print("=" * 50)
            print(f"S3 URI:      {s3_uri}")
            print(f"Patch ID:    {args.patch_id}")
            print(f"Commit:      {commit_hash}")
            print(f"Size:        {tarball_size / 1024 / 1024:.2f} MB")
            if args.trigger:
                print(f"Execution:   {result.get('execution_arn', 'N/A')}")
            print("=" * 50)
            print("\nTo trigger the workflow manually:")
            print("  aws stepfunctions start-execution \\")
            print(
                f"    --state-machine-arn arn:aws:states:us-east-1:$(aws sts get-caller-identity --query Account --output text):stateMachine:aura-hitl-patch-workflow-{args.environment} \\"
            )

            # Build example input JSON
            example_input = {
                "patch_id": args.patch_id,
                "code_source": s3_uri,
                "test_suite": args.test_suite,
                "severity": args.severity,
                "vulnerability_id": args.vulnerability_id or f"VULN-{args.patch_id}",
                "branch": "main",
                "timeout_minutes": 30,
                "security_group_id": "<SG_ID>",
                "subnet_ids": ["<SUBNET_1>", "<SUBNET_2>"],
            }
            print(f"    --input '{json.dumps(example_input)}'")


if __name__ == "__main__":
    main()
