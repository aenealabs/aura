#!/usr/bin/env python3
"""
BuildSpec Executor - Executes modular buildspec phases

This script parses and executes individual layer buildspecs,
allowing the orchestrator to call each layer's deployment logic.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml


def run_command(cmd: str, shell: bool = True) -> int:
    """Run a shell command and stream output."""
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=shell, env=os.environ.copy())
    return result.returncode


def execute_buildspec(buildspec_path: Path, environment: str):
    """Execute a buildspec file's build phases."""

    if not buildspec_path.exists():
        print(f"ERROR: Buildspec not found: {buildspec_path}")
        return 1

    print(f"Loading buildspec: {buildspec_path}")

    with open(buildspec_path) as f:
        buildspec = yaml.safe_load(f)

    # Set environment variables from buildspec
    if "env" in buildspec and "variables" in buildspec["env"]:
        for key, value in buildspec["env"]["variables"].items():
            os.environ[key] = str(value)

    os.environ["ENVIRONMENT"] = environment

    # Execute phases
    phases = buildspec.get("phases", {})

    for phase_name in ["pre_build", "build", "post_build"]:
        if phase_name not in phases:
            continue

        phase = phases[phase_name]
        commands = phase.get("commands", [])

        if not commands:
            continue

        print(f"\n{'='*60}")
        print(f"Phase: {phase_name}")
        print(f"{'='*60}")

        for command in commands:
            # Skip comments
            if command.strip().startswith("#"):
                print(command)
                continue

            # Execute command
            returncode = run_command(command)

            if returncode != 0:
                print(f"ERROR: Command failed with exit code {returncode}")
                print(f"Command: {command}")
                return returncode

    return 0


def main():
    parser = argparse.ArgumentParser(description="Execute a layer buildspec")
    parser.add_argument(
        "--layer", required=True, help="Layer name (e.g., data, compute)"
    )
    parser.add_argument(
        "--environment", required=True, help="Environment (e.g., dev, qa, prod)"
    )

    args = parser.parse_args()

    # Find repo root
    try:
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
        os.chdir(repo_root)
    except Exception as e:
        print(f"Warning: Could not find git root: {e}")

    buildspec_path = Path(f"deploy/buildspecs/buildspec-{args.layer}.yml")

    returncode = execute_buildspec(buildspec_path, args.environment)
    sys.exit(returncode)


if __name__ == "__main__":
    main()
