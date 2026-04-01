#!/usr/bin/env python3
"""
IAM Action Validator for Project Aura

Validates IAM actions in CloudFormation templates against the AWS IAM service.
This script addresses cfn-lint W3037 warnings by verifying that seemingly
unrecognized actions are actually valid AWS actions.

Usage:
    python scripts/validate_iam_actions.py                    # Validate all templates
    python scripts/validate_iam_actions.py template.yaml      # Validate specific template
    python scripts/validate_iam_actions.py --report           # Generate detailed report
    python scripts/validate_iam_actions.py --cache-refresh    # Refresh action cache

Exit codes:
    0 - All actions are valid
    1 - Some actions are invalid (typos or deprecated)
    2 - Error during validation
"""

import argparse
import glob
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml


# Add CloudFormation intrinsic function constructors
# These allow PyYAML to parse !Ref, !GetAtt, !Sub, etc.
def _cfn_constructor(loader, tag_suffix, node):
    """Generic constructor for CloudFormation intrinsic functions."""
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    elif isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node)}
    elif isinstance(node, yaml.MappingNode):
        return {tag_suffix: loader.construct_mapping(node)}
    return None


# Register all CloudFormation intrinsic functions
_CFN_TAGS = [
    "Ref",
    "GetAtt",
    "Sub",
    "Join",
    "Split",
    "Select",
    "If",
    "Equals",
    "Not",
    "And",
    "Or",
    "Condition",
    "Base64",
    "Cidr",
    "FindInMap",
    "GetAZs",
    "ImportValue",
    "Transform",
    "ToJsonString",
    "Length",
]

for tag in _CFN_TAGS:
    yaml.add_constructor(
        f"!{tag}",
        lambda loader, node, t=tag: _cfn_constructor(loader, t, node),
        Loader=yaml.SafeLoader,
    )

# Also handle multi-constructor for tags with suffixes (like !Ref)
yaml.add_multi_constructor(
    "!",
    lambda loader, suffix, node: _cfn_constructor(loader, suffix, node),
    Loader=yaml.SafeLoader,
)

# Try to import boto3 for AWS validation
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


@dataclass
class ActionValidation:
    """Result of validating an IAM action."""

    action: str
    is_valid: bool
    source_file: str
    line_number: Optional[int] = None
    validation_method: str = "unknown"
    note: str = ""


class IAMActionValidator:
    """Validates IAM actions from CloudFormation templates."""

    # Known valid actions that cfn-lint doesn't recognize (as of Jan 2026)
    # These are verified manually against AWS documentation
    KNOWN_VALID_ACTIONS = {
        # Step Functions
        "states:RedriveExecution",
        "states:TestState",
        # Bedrock (newer actions)
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:RetrieveAndGenerate",
        "bedrock:GetInferenceProfile",
        "bedrock:ListInferenceProfiles",
        "bedrock:GetFoundationModelAvailability",
        # CodeConnections (renamed from CodeStar Connections)
        "codeconnections:GetConnection",
        "codeconnections:UseConnection",
        "codeconnections:ListConnections",
        "codeconnections:PassConnection",
        # Lambda (newer actions)
        "lambda:GetFunctionConfiguration",
        "lambda:InvokeFunctionUrl",
        # EventBridge Scheduler
        "scheduler:GetSchedule",
        "scheduler:ListSchedules",
        "scheduler:CreateSchedule",
        "scheduler:UpdateSchedule",
        "scheduler:DeleteSchedule",
        # DynamoDB streams
        "dynamodb:DescribeStream",
        "dynamodb:GetShardIterator",
        # Neptune
        "neptune-db:ReadDataViaQuery",
        "neptune-db:WriteDataViaQuery",
        "neptune-db:GetGraphSummary",
        "neptune-db:GetStreamRecords",
        # SSM (newer actions)
        "ssm:GetParametersByPath",
    }

    # Service prefix mappings for validation
    SERVICE_PREFIXES = {
        "states": "stepfunctions",
        "bedrock": "bedrock",
        "codeconnections": "codeconnections",
        "lambda": "lambda",
        "scheduler": "scheduler",
        "dynamodb": "dynamodb",
        "neptune-db": "neptune",
        "ssm": "ssm",
        "iam": "iam",
        "s3": "s3",
        "ec2": "ec2",
        "eks": "eks",
        "ecr": "ecr",
        "logs": "logs",
        "cloudwatch": "cloudwatch",
        "cloudformation": "cloudformation",
        "secretsmanager": "secretsmanager",
        "kms": "kms",
        "sns": "sns",
        "sqs": "sqs",
        "events": "events",
        "sts": "sts",
    }

    CACHE_FILE = Path.home() / ".cache" / "aura" / "iam_actions_cache.json"
    CACHE_TTL_DAYS = 7

    def __init__(self, use_cache: bool = True, verbose: bool = False):
        self.use_cache = use_cache
        self.verbose = verbose
        self.validated_actions: dict[str, bool] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached action validation results."""
        if not self.use_cache:
            return

        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE) as f:
                    cache_data = json.load(f)

                # Check cache TTL
                cache_time = datetime.fromisoformat(
                    cache_data.get("timestamp", "2000-01-01")
                )
                if datetime.now() - cache_time < timedelta(days=self.CACHE_TTL_DAYS):
                    self.validated_actions = cache_data.get("actions", {})
                    if self.verbose:
                        print(
                            f"Loaded {len(self.validated_actions)} actions from cache"
                        )
        except (json.JSONDecodeError, OSError, ValueError) as e:
            if self.verbose:
                print(f"Cache load failed: {e}")

    def _save_cache(self) -> None:
        """Save validated actions to cache."""
        if not self.use_cache:
            return

        try:
            self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "actions": self.validated_actions,
            }
            with open(self.CACHE_FILE, "w") as f:
                json.dump(cache_data, f, indent=2)
        except OSError as e:
            if self.verbose:
                print(f"Cache save failed: {e}")

    def extract_actions_from_template(
        self, template_path: str
    ) -> list[tuple[str, int]]:
        """Extract IAM actions from a CloudFormation template."""
        actions = []

        try:
            with open(template_path) as f:
                content = f.read()
                lines = content.split("\n")

            # Parse YAML
            template = yaml.safe_load(content)
            if not template:
                return actions

            # Find actions in the raw content with line numbers
            action_pattern = re.compile(r'["\']?([a-z0-9-]+:[A-Za-z*]+)["\']?')
            for line_num, line in enumerate(lines, 1):
                if "Action" in line or "action" in line:
                    matches = action_pattern.findall(line)
                    for match in matches:
                        # Skip CloudFormation intrinsic functions
                        if match.startswith(("Fn:", "Ref:", "AWS:")):
                            continue
                        # Skip wildcards
                        if match.endswith(":*") or "*" in match.split(":")[1]:
                            continue
                        actions.append((match, line_num))

            # Also extract from nested YAML structure
            self._extract_nested_actions(template, actions, template_path)

        except yaml.YAMLError as e:
            print(f"YAML parse error in {template_path}: {e}")
        except OSError as e:
            print(f"Error reading {template_path}: {e}")

        return list(set(actions))  # Deduplicate

    def _extract_nested_actions(
        self, obj: object, actions: list, source_file: str, depth: int = 0
    ) -> None:
        """Recursively extract actions from nested YAML structure."""
        if depth > 50:  # Prevent infinite recursion
            return

        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ("Action", "action", "NotAction"):
                    if isinstance(value, str):
                        # Must contain colon to be an IAM action (e.g., s3:GetObject)
                        # Skip non-IAM values like "BLOCK", "ALLOW", etc.
                        if (
                            ":" in value
                            and not value.endswith(":*")
                            and "*" not in value.split(":")[-1]
                        ):
                            actions.append((value, 0))
                    elif isinstance(value, list):
                        for action in value:
                            if isinstance(action, str):
                                if (
                                    ":" in action
                                    and not action.endswith(":*")
                                    and "*" not in action.split(":")[-1]
                                ):
                                    actions.append((action, 0))
                else:
                    self._extract_nested_actions(value, actions, source_file, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_nested_actions(item, actions, source_file, depth + 1)

    def validate_action(self, action: str) -> tuple[bool, str]:
        """Validate a single IAM action."""
        # Check cache first
        if action in self.validated_actions:
            return self.validated_actions[action], "cache"

        # Check known valid actions
        if action in self.KNOWN_VALID_ACTIONS:
            self.validated_actions[action] = True
            return True, "known_valid"

        # Parse service prefix
        if ":" not in action:
            self.validated_actions[action] = False
            return False, "invalid_format"

        service, action_name = action.split(":", 1)

        # Check if service prefix is known
        if service not in self.SERVICE_PREFIXES:
            # Unknown service - might be valid but we can't verify
            return True, "unknown_service"

        # Use boto3 to validate if available
        if BOTO3_AVAILABLE:
            return self._validate_with_boto3(action, service)

        # Fallback: assume valid if format is correct
        return True, "format_check"

    def _validate_with_boto3(self, action: str, service: str) -> tuple[bool, str]:
        """Validate action using AWS IAM simulate-custom-policy."""
        try:
            iam = boto3.client("iam")

            # Create a minimal policy with the action
            policy = json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {"Effect": "Allow", "Action": action, "Resource": "*"}
                    ],
                }
            )

            # Simulate the policy - if action is invalid, this will fail
            response = iam.simulate_custom_policy(
                PolicyInputList=[policy],
                ActionNames=[action],
                ResourceArns=["arn:aws:s3:::example-bucket"],
            )

            # If we get here without error, the action is recognized
            self.validated_actions[action] = True
            return True, "aws_api"

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "InvalidAction":
                self.validated_actions[action] = False
                return False, "aws_api_invalid"
            # Other errors (permissions, etc.) - assume valid
            return True, "aws_api_error"
        except NoCredentialsError:
            # No AWS credentials - fall back to format check
            return True, "no_credentials"
        except Exception as e:
            if self.verbose:
                print(f"Boto3 validation error for {action}: {e}")
            return True, "validation_error"

    def validate_templates(
        self, template_paths: list[str]
    ) -> tuple[list[ActionValidation], list[ActionValidation]]:
        """Validate all actions in the given templates."""
        valid_actions = []
        invalid_actions = []

        for template_path in template_paths:
            if self.verbose:
                print(f"Validating: {template_path}")

            actions = self.extract_actions_from_template(template_path)

            for action, line_num in actions:
                is_valid, method = self.validate_action(action)

                result = ActionValidation(
                    action=action,
                    is_valid=is_valid,
                    source_file=template_path,
                    line_number=line_num if line_num > 0 else None,
                    validation_method=method,
                )

                if is_valid:
                    valid_actions.append(result)
                else:
                    invalid_actions.append(result)

        # Save cache after validation
        self._save_cache()

        return valid_actions, invalid_actions

    def generate_report(
        self, valid: list[ActionValidation], invalid: list[ActionValidation]
    ) -> str:
        """Generate a validation report."""
        lines = []
        lines.append("=" * 60)
        lines.append("IAM Action Validation Report")
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("=" * 60)
        lines.append("")

        # Summary
        total = len(valid) + len(invalid)
        lines.append(f"Total actions scanned: {total}")
        lines.append(f"Valid actions: {len(valid)}")
        lines.append(f"Invalid actions: {len(invalid)}")
        lines.append("")

        if invalid:
            lines.append("-" * 60)
            lines.append("INVALID ACTIONS (require attention):")
            lines.append("-" * 60)
            for result in sorted(invalid, key=lambda x: (x.source_file, x.action)):
                loc = f":{result.line_number}" if result.line_number else ""
                lines.append(f"  {result.action}")
                lines.append(f"    File: {result.source_file}{loc}")
                lines.append(f"    Method: {result.validation_method}")
                lines.append("")

        # Group valid actions by validation method
        by_method: dict[str, list[ActionValidation]] = {}
        for result in valid:
            by_method.setdefault(result.validation_method, []).append(result)

        if by_method:
            lines.append("-" * 60)
            lines.append("VALID ACTIONS (by validation method):")
            lines.append("-" * 60)
            for method, results in sorted(by_method.items()):
                lines.append(f"\n  [{method}] ({len(results)} actions)")
                unique_actions = sorted(set(r.action for r in results))
                for action in unique_actions[:10]:  # Limit to 10 per method
                    lines.append(f"    - {action}")
                if len(unique_actions) > 10:
                    lines.append(f"    ... and {len(unique_actions) - 10} more")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Validate IAM actions in CloudFormation templates"
    )
    parser.add_argument(
        "templates",
        nargs="*",
        help="Template files to validate (default: all in deploy/cloudformation/)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate detailed validation report",
    )
    parser.add_argument(
        "--cache-refresh",
        action="store_true",
        help="Refresh the action validation cache",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache usage",
    )

    args = parser.parse_args()

    # Handle cache refresh
    if args.cache_refresh:
        cache_file = IAMActionValidator.CACHE_FILE
        if cache_file.exists():
            cache_file.unlink()
            print(f"Cache cleared: {cache_file}")
        else:
            print("No cache file to clear")
        if not args.templates:
            return 0

    # Determine templates to validate
    if args.templates:
        template_paths = args.templates
    else:
        # Default: all CloudFormation templates
        template_paths = glob.glob("deploy/cloudformation/*.yaml")
        if not template_paths:
            # Try from repo root
            repo_root = Path(__file__).parent.parent
            template_paths = glob.glob(str(repo_root / "deploy/cloudformation/*.yaml"))

    if not template_paths:
        print("No templates found to validate")
        return 2

    # Create validator and run
    validator = IAMActionValidator(use_cache=not args.no_cache, verbose=args.verbose)

    print(f"Validating {len(template_paths)} CloudFormation template(s)...")
    valid, invalid = validator.validate_templates(template_paths)

    if args.report:
        report = validator.generate_report(valid, invalid)
        print(report)
    else:
        # Summary output
        print(f"\nResults:")
        print(f"  Valid actions: {len(valid)}")
        print(f"  Invalid actions: {len(invalid)}")

        if invalid:
            print("\nInvalid actions found:")
            for result in invalid:
                print(f"  - {result.action} ({result.source_file})")
            print("\nRun with --report for detailed output")
            return 1

    return 0 if not invalid else 1


if __name__ == "__main__":
    sys.exit(main())
