#!/usr/bin/env python3
"""
Change Detection Script for Modular Infrastructure Deployment

Detects which CloudFormation stacks have changed based on git diff
and outputs a JSON configuration for the build orchestrator.

Usage:
    python3 detect_changes.py [--base-ref COMMIT] [--force-all]
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set

# Define infrastructure layers and their dependencies
# This structure makes it easy to split into separate CodeBuild projects later
INFRASTRUCTURE_LAYERS = {
    "foundation": {
        "name": "Foundation Layer",
        "stacks": ["networking", "security", "iam"],
        "files": [
            "deploy/cloudformation/networking.yaml",
            "deploy/cloudformation/security.yaml",
            "deploy/cloudformation/iam.yaml",
        ],
        "buildspec": "deploy/buildspecs/buildspec-foundation.yml",
        "dependencies": [],
        "description": "VPC, Security Groups, IAM Roles",
    },
    "data": {
        "name": "Data Layer",
        "stacks": ["neptune", "opensearch", "dynamodb", "s3"],
        "files": [
            "deploy/cloudformation/neptune-simplified.yaml",
            "deploy/cloudformation/opensearch.yaml",
            "deploy/cloudformation/dynamodb.yaml",
            "deploy/cloudformation/s3.yaml",
        ],
        "buildspec": "deploy/buildspecs/buildspec-data.yml",
        "dependencies": ["foundation"],
        "description": "Databases and Storage",
    },
    "compute": {
        "name": "Compute Layer",
        "stacks": ["eks"],
        "files": [
            "deploy/cloudformation/eks.yaml",
        ],
        "buildspec": "deploy/buildspecs/buildspec-compute.yml",
        "dependencies": ["foundation"],
        "description": "EKS Cluster and Node Groups",
    },
    "application": {
        "name": "Application Layer",
        "stacks": ["aura-bedrock-infrastructure"],
        "files": [
            "deploy/cloudformation/aura-bedrock-infrastructure.yaml",
        ],
        "buildspec": "deploy/buildspecs/buildspec-application.yml",
        "dependencies": ["foundation", "data", "compute"],
        "description": "Application-specific Infrastructure",
    },
    "observability": {
        "name": "Observability Layer",
        "stacks": ["secrets", "monitoring", "aura-cost-alerts"],
        "files": [
            "deploy/cloudformation/secrets.yaml",
            "deploy/cloudformation/monitoring.yaml",
            "deploy/cloudformation/aura-cost-alerts.yaml",
        ],
        "buildspec": "deploy/buildspecs/buildspec-observability.yml",
        "dependencies": ["foundation", "data"],
        "description": "Secrets, Monitoring, Alerts",
    },
}


def run_command(cmd: List[str], check: bool = True) -> str:
    """Run a shell command and return output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if not check:
            return ""
        print(f"Error running command: {' '.join(cmd)}", file=sys.stderr)
        print(f"Error: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def get_changed_files(base_ref: str = None) -> Set[str]:
    """Get list of changed files using git diff."""
    if base_ref is None:
        # Try to detect the base ref automatically based on branch context
        current_branch = run_command(["git", "branch", "--show-current"], check=False)

        if current_branch == "main" or current_branch == "master":
            # Main branch deployment: Compare against HEAD~1 (previous commit)
            # This ensures we detect changes in the latest commit on main
            base_ref = "HEAD~1"
            print(f"Main branch deployment detected", file=sys.stderr)
        else:
            # Feature branch deployment: Compare against merge base with origin/main
            base_ref = run_command(
                ["git", "merge-base", "HEAD", "origin/main"], check=False
            )
            if not base_ref:
                # Fall back to HEAD~1 if we can't find merge base
                base_ref = "HEAD~1"
            print(
                f"Feature branch '{current_branch}' deployment detected",
                file=sys.stderr,
            )

    print(f"Comparing against: {base_ref}", file=sys.stderr)

    # Get changed files
    diff_output = run_command(
        ["git", "diff", "--name-only", base_ref, "HEAD"], check=False
    )

    # Check if git diff failed (shallow clone in CodeBuild)
    if not diff_output and base_ref == "HEAD~1":
        print("WARNING: Shallow git clone detected (CodeBuild)", file=sys.stderr)
        print(
            "Cannot determine changed files - will deploy ALL layers", file=sys.stderr
        )
        return None  # Signal to caller to use --force-all logic

    changed_files = set()
    if diff_output:
        changed_files = set(diff_output.split("\n"))

    # Also check for uncommitted changes (useful for local testing)
    uncommitted = run_command(["git", "diff", "--name-only", "HEAD"], check=False)
    if uncommitted:
        changed_files.update(uncommitted.split("\n"))

    return changed_files


def detect_changed_layers(changed_files: Set[str], force_all: bool = False) -> Dict:
    """Detect which infrastructure layers have changed."""
    if force_all:
        print("Force flag set - deploying all layers", file=sys.stderr)
        changed_layers = list(INFRASTRUCTURE_LAYERS.keys())
    else:
        changed_layers = []

        for layer_id, layer_config in INFRASTRUCTURE_LAYERS.items():
            # Check if any files in this layer have changed
            for file_pattern in layer_config["files"]:
                if file_pattern in changed_files:
                    print(
                        f"Detected change in {layer_id}: {file_pattern}",
                        file=sys.stderr,
                    )
                    changed_layers.append(layer_id)
                    break

        # Check for changes in master-stack.yaml - redeploy everything
        if "deploy/cloudformation/master-stack.yaml" in changed_files:
            print("Master stack changed - deploying all layers", file=sys.stderr)
            changed_layers = list(INFRASTRUCTURE_LAYERS.keys())

    # Add dependencies for changed layers
    layers_to_deploy = set(changed_layers)
    for layer_id in changed_layers:
        dependencies = INFRASTRUCTURE_LAYERS[layer_id]["dependencies"]
        layers_to_deploy.update(dependencies)

    # Sort layers by deployment order (respecting dependencies)
    deployment_order = []
    remaining = set(layers_to_deploy)

    while remaining:
        # Find layers with all dependencies satisfied
        ready = [
            layer_id
            for layer_id in remaining
            if all(
                dep in deployment_order
                for dep in INFRASTRUCTURE_LAYERS[layer_id]["dependencies"]
            )
        ]

        if not ready:
            print("Error: Circular dependency detected!", file=sys.stderr)
            sys.exit(1)

        deployment_order.extend(sorted(ready))  # Sort for deterministic order
        remaining -= set(ready)

    return {
        "changed_layers": changed_layers,
        "layers_to_deploy": deployment_order,
        "layer_configs": {
            layer_id: INFRASTRUCTURE_LAYERS[layer_id] for layer_id in deployment_order
        },
    }


def get_deployed_stacks(environment: str = "dev") -> Set[str]:
    """Get list of already-deployed CloudFormation stacks."""
    try:
        import boto3

        cfn = boto3.client("cloudformation")

        # List all stacks with CREATE_COMPLETE or UPDATE_COMPLETE status
        response = cfn.list_stacks(
            StackStatusFilter=["CREATE_COMPLETE", "UPDATE_COMPLETE"]
        )

        deployed_stacks = set()
        for stack in response["StackSummaries"]:
            stack_name = stack["StackName"]
            # Extract stack type from name (e.g., "aura-neptune-dev" -> "neptune")
            if stack_name.startswith(f"aura-"):
                parts = stack_name.split("-")
                if len(parts) >= 2 and parts[-1] == environment:
                    stack_type = "-".join(
                        parts[1:-1]
                    )  # Handle multi-part names like "aura-cost-alerts-dev"
                    deployed_stacks.add(stack_type)

        return deployed_stacks
    except Exception as e:
        print(f"Warning: Could not check deployed stacks: {e}", file=sys.stderr)
        return set()


def detect_missing_layers(environment: str = "dev") -> list:
    """Detect which infrastructure layers are NOT yet deployed."""
    deployed_stacks = get_deployed_stacks(environment)

    print(f"Deployed stacks: {sorted(deployed_stacks)}", file=sys.stderr)

    missing_layers = []
    for layer_id, layer_config in INFRASTRUCTURE_LAYERS.items():
        # Check if ANY stack in this layer is missing
        layer_stacks = set(layer_config["stacks"])
        if not layer_stacks.issubset(deployed_stacks):
            missing_stacks = layer_stacks - deployed_stacks
            print(
                f"Layer '{layer_id}' is missing stacks: {missing_stacks}",
                file=sys.stderr,
            )
            missing_layers.append(layer_id)

    return missing_layers


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Detect infrastructure changes")
    parser.add_argument(
        "--base-ref", help="Git reference to compare against (default: auto-detect)"
    )
    parser.add_argument(
        "--force-all", action="store_true", help="Force deployment of all layers"
    )
    parser.add_argument(
        "--deploy-missing",
        action="store_true",
        help="Deploy layers that are not yet deployed in AWS",
    )
    parser.add_argument(
        "--environment", default="dev", help="Environment name (default: dev)"
    )
    parser.add_argument(
        "--output",
        default="/tmp/deployment-plan.json",  # nosec B108 - CI script output
        help="Output file for deployment plan",
    )

    args = parser.parse_args()

    # Change to repo root
    repo_root = run_command(["git", "rev-parse", "--show-toplevel"])
    os.chdir(repo_root)

    print("=" * 60, file=sys.stderr)
    print("Infrastructure Change Detection", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Detect changes
    force_all = args.force_all
    deploy_missing = args.deploy_missing

    if deploy_missing:
        # Deploy only layers that are not yet in AWS
        print(
            "\n--deploy-missing flag set: Checking AWS for undeployed stacks",
            file=sys.stderr,
        )
        missing_layers = detect_missing_layers(args.environment)
        changed_files = set()  # Not using file-based detection
        result = detect_changed_layers(changed_files, force_all=False)
        # Override with missing layers
        result["changed_layers"] = missing_layers

        # Get deployed stacks to filter dependencies
        deployed_stacks = get_deployed_stacks(args.environment)

        # Recalculate deployment order with dependencies
        # Only include dependencies that are NOT fully deployed
        layers_to_deploy = set(missing_layers)
        for layer_id in missing_layers:
            for dep_layer in INFRASTRUCTURE_LAYERS[layer_id]["dependencies"]:
                dep_stacks = set(INFRASTRUCTURE_LAYERS[dep_layer]["stacks"])
                # Only add dependency if it has missing stacks
                if not dep_stacks.issubset(deployed_stacks):
                    layers_to_deploy.add(dep_layer)

        # Sort by deployment order
        deployment_order = []
        remaining = set(layers_to_deploy)
        while remaining:
            ready = [
                layer_id
                for layer_id in remaining
                if all(
                    dep in deployment_order or dep not in layers_to_deploy
                    for dep in INFRASTRUCTURE_LAYERS[layer_id]["dependencies"]
                )
            ]
            if not ready:
                print("Error: Circular dependency detected!", file=sys.stderr)
                sys.exit(1)
            deployment_order.extend(sorted(ready))
            remaining -= set(ready)

        result["layers_to_deploy"] = deployment_order
        result["layer_configs"] = {
            layer_id: INFRASTRUCTURE_LAYERS[layer_id] for layer_id in deployment_order
        }
    elif force_all:
        changed_files = set()
        result = detect_changed_layers(changed_files, force_all)
    else:
        changed_files = get_changed_files(args.base_ref)
        # Handle shallow clone (CodeBuild) - deploy all layers
        if changed_files is None:
            force_all = True
            changed_files = set()
        else:
            print(f"\nChanged files: {len(changed_files)}", file=sys.stderr)
            if changed_files:
                for f in sorted(changed_files):
                    if f.startswith("deploy/cloudformation/"):
                        print(f"  - {f}", file=sys.stderr)

        # Detect layers
        result = detect_changed_layers(changed_files, force_all)

    print("\n" + "=" * 60, file=sys.stderr)
    print("Deployment Plan", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    if not result["layers_to_deploy"]:
        print(
            "\nNo infrastructure changes detected. Skipping deployment.",
            file=sys.stderr,
        )
    else:
        print(
            f"\nLayers to deploy ({len(result['layers_to_deploy'])}):", file=sys.stderr
        )
        for i, layer_id in enumerate(result["layers_to_deploy"], 1):
            layer = INFRASTRUCTURE_LAYERS[layer_id]
            changed = (
                "✓ CHANGED" if layer_id in result["changed_layers"] else "→ dependency"
            )
            print(
                f"  {i}. {layer['name']}: {layer['description']} [{changed}]",
                file=sys.stderr,
            )

    print("=" * 60, file=sys.stderr)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nDeployment plan written to: {args.output}", file=sys.stderr)

    # Also print to stdout for CodeBuild to consume
    print(json.dumps(result))


if __name__ == "__main__":
    main()
