"""ARN validation for Environment Validator (ADR-062).

Validates ARNs in Kubernetes resources to ensure they reference
the correct AWS account and region for the target environment.

Rules implemented:
- ENV-001: Account ID in ARNs must match target environment
- ENV-006: Region in ARNs must match target environment
- ENV-007: KMS key ARNs must be environment-specific
- ENV-008: IAM role ARNs must match target account
"""

import re
from dataclasses import dataclass
from typing import Generator, Optional

from src.services.env_validator.config import load_environment_registry
from src.services.env_validator.models import ManifestResource, Severity, Violation


@dataclass
class ParsedArn:
    """Parsed components of an AWS ARN."""

    partition: str  # aws, aws-cn, aws-us-gov
    service: str  # e.g., iam, s3, dynamodb
    region: str  # e.g., us-east-1 (empty for global services)
    account_id: str  # 12-digit account ID
    resource: str  # Resource type and identifier

    @classmethod
    def parse(cls, arn: str) -> Optional["ParsedArn"]:
        """Parse an ARN string into components.

        Args:
            arn: AWS ARN string

        Returns:
            ParsedArn if valid, None otherwise
        """
        # ARN format: arn:partition:service:region:account:resource
        pattern = (
            r"^arn:(aws|aws-cn|aws-us-gov):([a-zA-Z0-9-]+):([a-z0-9-]*):(\d*):(.+)$"
        )
        match = re.match(pattern, arn)
        if not match:
            return None

        return cls(
            partition=match.group(1),
            service=match.group(2),
            region=match.group(3),
            account_id=match.group(4),
            resource=match.group(5),
        )


# ARN pattern to find ARNs in text
ARN_PATTERN = re.compile(
    r"arn:(aws|aws-cn|aws-us-gov):[a-zA-Z0-9-]+:[a-z0-9-]*:\d*:[^\s\"']+"
)


def extract_arns(value: str) -> list[str]:
    """Extract all ARNs from a string value.

    Args:
        value: String that may contain ARNs

    Returns:
        List of ARN strings found
    """
    return ARN_PATTERN.findall(value) if isinstance(value, str) else []


def find_arns_in_dict(
    data: dict, path: str = ""
) -> Generator[tuple[str, str], None, None]:
    """Recursively find all ARNs in a dictionary.

    Args:
        data: Dictionary to search
        path: Current path for reporting

    Yields:
        Tuples of (field_path, arn_value)
    """
    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key

        if isinstance(value, str):
            # Check if the value itself is an ARN or contains ARNs
            if value.startswith("arn:"):
                yield current_path, value
            else:
                # Look for embedded ARNs (e.g., in annotations)
                for match in ARN_PATTERN.finditer(value):
                    yield current_path, match.group(0)
        elif isinstance(value, dict):
            yield from find_arns_in_dict(value, current_path)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str) and item.startswith("arn:"):
                    yield f"{current_path}[{i}]", item
                elif isinstance(item, dict):
                    yield from find_arns_in_dict(item, f"{current_path}[{i}]")


class ArnValidator:
    """Validates ARNs in Kubernetes resources for environment consistency."""

    def __init__(self, target_env: str):
        """Initialize validator.

        Args:
            target_env: Target environment name (dev, qa, staging, prod)
        """
        self.target_env = target_env
        self.registry = load_environment_registry()
        self.env_config = self.registry.get(target_env)

        if not self.env_config:
            raise ValueError(f"Unknown environment: {target_env}")

    def validate(self, resource: ManifestResource) -> list[Violation]:
        """Validate all ARNs in a Kubernetes resource.

        Args:
            resource: Kubernetes resource to validate

        Returns:
            List of violations found
        """
        violations = []

        for field_path, arn in find_arns_in_dict(resource.raw):
            parsed = ParsedArn.parse(arn)
            if not parsed:
                continue  # Skip malformed ARNs

            # Check each rule
            violations.extend(self._check_account_id(resource, field_path, arn, parsed))
            violations.extend(self._check_region(resource, field_path, arn, parsed))
            violations.extend(self._check_kms(resource, field_path, arn, parsed))
            violations.extend(self._check_iam_role(resource, field_path, arn, parsed))

        return violations

    def _check_account_id(
        self,
        resource: ManifestResource,
        field_path: str,
        arn: str,
        parsed: ParsedArn,
    ) -> list[Violation]:
        """Check ENV-001: Account ID must match target environment."""
        violations = []

        # Skip if account ID is empty (global resources like S3 buckets in some ARN formats)
        if not parsed.account_id:
            return violations

        expected_account = self.env_config.account_id
        if parsed.account_id != expected_account:
            # Detect which environment this ARN belongs to
            detected_env = self.registry.detect_environment_from_account(
                parsed.account_id
            )
            env_hint = f" (belongs to {detected_env})" if detected_env else ""

            violations.append(
                Violation(
                    rule_id="ENV-001",
                    severity=Severity.CRITICAL,
                    resource_type=resource.kind,
                    resource_name=resource.name,
                    field_path=field_path,
                    expected_value=expected_account,
                    actual_value=parsed.account_id,
                    message=f"ARN contains account {parsed.account_id}{env_hint}, expected {expected_account} ({self.target_env})",
                    suggested_fix=f"Update ARN to use account {expected_account}",
                    auto_remediable=False,
                )
            )

        return violations

    def _check_region(
        self,
        resource: ManifestResource,
        field_path: str,
        arn: str,
        parsed: ParsedArn,
    ) -> list[Violation]:
        """Check ENV-006: Region must match target environment."""
        violations = []

        # Skip global services (IAM, S3 bucket names, etc.)
        global_services = {"iam", "s3", "cloudfront", "route53", "organizations"}
        if parsed.service in global_services or not parsed.region:
            return violations

        expected_region = self.env_config.region
        if parsed.region != expected_region:
            violations.append(
                Violation(
                    rule_id="ENV-006",
                    severity=Severity.CRITICAL,
                    resource_type=resource.kind,
                    resource_name=resource.name,
                    field_path=field_path,
                    expected_value=expected_region,
                    actual_value=parsed.region,
                    message=f"ARN region {parsed.region} does not match target environment region {expected_region}",
                    suggested_fix=f"Update ARN to use region {expected_region}",
                    auto_remediable=False,
                )
            )

        return violations

    def _check_kms(
        self,
        resource: ManifestResource,
        field_path: str,
        arn: str,
        parsed: ParsedArn,
    ) -> list[Violation]:
        """Check ENV-007: KMS key ARNs must be environment-specific."""
        violations = []

        if parsed.service != "kms":
            return violations

        # KMS keys should have environment suffix in alias or key ID
        resource_suffix = self.env_config.resource_suffix
        if resource_suffix not in parsed.resource.lower():
            # Check if it's a cross-environment reference
            for other_env in self.registry.get_other_environments(self.target_env):
                other_config = self.registry.get(other_env)
                if (
                    other_config
                    and other_config.resource_suffix in parsed.resource.lower()
                ):
                    violations.append(
                        Violation(
                            rule_id="ENV-007",
                            severity=Severity.CRITICAL,
                            resource_type=resource.kind,
                            resource_name=resource.name,
                            field_path=field_path,
                            expected_value=f"KMS key with {resource_suffix}",
                            actual_value=arn,
                            message=f"KMS key ARN references {other_env} environment instead of {self.target_env}",
                            suggested_fix=f"Use KMS key with {resource_suffix} suffix",
                            auto_remediable=False,
                        )
                    )
                    break

        return violations

    def _check_iam_role(
        self,
        resource: ManifestResource,
        field_path: str,
        arn: str,
        parsed: ParsedArn,
    ) -> list[Violation]:
        """Check ENV-008: IAM role ARNs must match target account."""
        violations = []

        if parsed.service != "iam":
            return violations

        # IAM roles should be in the correct account
        expected_account = self.env_config.account_id
        if parsed.account_id and parsed.account_id != expected_account:
            detected_env = self.registry.detect_environment_from_account(
                parsed.account_id
            )
            env_hint = f" ({detected_env})" if detected_env else ""

            violations.append(
                Violation(
                    rule_id="ENV-008",
                    severity=Severity.CRITICAL,
                    resource_type=resource.kind,
                    resource_name=resource.name,
                    field_path=field_path,
                    expected_value=expected_account,
                    actual_value=parsed.account_id,
                    message=f"IAM role ARN references account {parsed.account_id}{env_hint} instead of {expected_account} ({self.target_env})",
                    suggested_fix=f"Update IAM role ARN to use account {expected_account}",
                    auto_remediable=False,
                )
            )

        return violations
