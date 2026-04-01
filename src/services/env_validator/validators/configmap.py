"""ConfigMap validation for Environment Validator (ADR-062).

Validates ConfigMap resources to ensure they contain
environment-appropriate values.

Rules implemented:
- ENV-003: DynamoDB table names must contain correct env suffix
- ENV-004: Neptune/OpenSearch endpoints must match environment
- ENV-005: SNS/SQS ARNs must reference correct account
- ENV-101: ENVIRONMENT variable should match deployment target
- ENV-102: Secret references should use environment-specific paths
"""

import re

from src.services.env_validator.config import (
    detect_environment_in_string,
    load_environment_registry,
)
from src.services.env_validator.models import ManifestResource, Severity, Violation


class ConfigMapValidator:
    """Validates ConfigMap resources for environment consistency."""

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
        """Validate a ConfigMap resource.

        Args:
            resource: ConfigMap Kubernetes resource

        Returns:
            List of violations found
        """
        if resource.kind != "ConfigMap":
            return []

        violations = []
        data = resource.raw.get("data", {})

        for key, value in data.items():
            if not isinstance(value, str):
                continue

            # Check specific rules based on key patterns
            violations.extend(self._check_dynamodb_tables(resource, key, value))
            violations.extend(self._check_endpoints(resource, key, value))
            violations.extend(self._check_environment_var(resource, key, value))
            violations.extend(self._check_secret_refs(resource, key, value))
            violations.extend(self._check_sns_sqs(resource, key, value))

        return violations

    def _check_dynamodb_tables(
        self, resource: ManifestResource, key: str, value: str
    ) -> list[Violation]:
        """Check ENV-003: DynamoDB table names must have correct suffix."""
        violations = []

        # Look for DynamoDB table name patterns
        table_indicators = ["TABLE", "DYNAMODB", "_TABLE_NAME"]
        is_table_ref = any(ind in key.upper() for ind in table_indicators)

        if not is_table_ref:
            return violations

        # Check if table name contains wrong environment suffix
        detected_env = detect_environment_in_string(value)
        if detected_env and detected_env != self.target_env:
            violations.append(
                Violation(
                    rule_id="ENV-003",
                    severity=Severity.CRITICAL,
                    resource_type=resource.kind,
                    resource_name=resource.name,
                    field_path=f"data.{key}",
                    expected_value=f"*{self.env_config.resource_suffix}",
                    actual_value=value,
                    message=f"DynamoDB table '{value}' appears to be for {detected_env}, not {self.target_env}",
                    suggested_fix=f"Use table name ending in {self.env_config.resource_suffix}",
                    auto_remediable=False,
                )
            )
        elif not detected_env and not value.endswith(self.env_config.resource_suffix):
            # Table name doesn't have any recognized environment suffix
            if value.startswith("aura-"):
                violations.append(
                    Violation(
                        rule_id="ENV-003",
                        severity=Severity.CRITICAL,
                        resource_type=resource.kind,
                        resource_name=resource.name,
                        field_path=f"data.{key}",
                        expected_value=f"*{self.env_config.resource_suffix}",
                        actual_value=value,
                        message=f"DynamoDB table '{value}' missing environment suffix {self.env_config.resource_suffix}",
                        suggested_fix=f"Add {self.env_config.resource_suffix} suffix to table name",
                        auto_remediable=False,
                    )
                )

        return violations

    def _check_endpoints(
        self, resource: ManifestResource, key: str, value: str
    ) -> list[Violation]:
        """Check ENV-004: Neptune/OpenSearch endpoints must match environment."""
        violations = []

        # Check for Neptune endpoints
        if "NEPTUNE" in key.upper() or "neptune" in value.lower():
            violations.extend(
                self._validate_endpoint(
                    resource, key, value, "Neptune", self.env_config.neptune_cluster
                )
            )

        # Check for OpenSearch endpoints
        if "OPENSEARCH" in key.upper() or "es.amazonaws.com" in value.lower():
            violations.extend(
                self._validate_endpoint(
                    resource,
                    key,
                    value,
                    "OpenSearch",
                    self.env_config.opensearch_domain,
                )
            )

        return violations

    def _validate_endpoint(
        self,
        resource: ManifestResource,
        key: str,
        value: str,
        service_name: str,
        expected_pattern: str,
    ) -> list[Violation]:
        """Validate an endpoint value against expected pattern."""
        violations = []

        # Check if endpoint contains wrong environment
        detected_env = detect_environment_in_string(value)
        if detected_env and detected_env != self.target_env:
            violations.append(
                Violation(
                    rule_id="ENV-004",
                    severity=Severity.CRITICAL,
                    resource_type=resource.kind,
                    resource_name=resource.name,
                    field_path=f"data.{key}",
                    expected_value=f"{service_name} endpoint for {self.target_env}",
                    actual_value=value,
                    message=f"{service_name} endpoint '{value}' appears to be for {detected_env}, not {self.target_env}",
                    suggested_fix=f"Use {self.target_env} {service_name} endpoint",
                    auto_remediable=False,
                )
            )

        return violations

    def _check_environment_var(
        self, resource: ManifestResource, key: str, value: str
    ) -> list[Violation]:
        """Check ENV-101: ENVIRONMENT variable should match target."""
        violations = []

        if key.upper() == "ENVIRONMENT":
            if value.lower() != self.target_env.lower():
                violations.append(
                    Violation(
                        rule_id="ENV-101",
                        severity=Severity.WARNING,
                        resource_type=resource.kind,
                        resource_name=resource.name,
                        field_path=f"data.{key}",
                        expected_value=self.target_env,
                        actual_value=value,
                        message=f"ENVIRONMENT variable is '{value}', expected '{self.target_env}'",
                        suggested_fix=f"Set ENVIRONMENT to '{self.target_env}'",
                        auto_remediable=True,  # Safe to auto-fix
                    )
                )

        return violations

    def _check_secret_refs(
        self, resource: ManifestResource, key: str, value: str
    ) -> list[Violation]:
        """Check ENV-102: Secret references should use environment-specific paths."""
        violations = []

        # Look for Secrets Manager or SSM paths
        secret_patterns = [
            (r"/aura/(\w+)/", "secrets path"),
            (r"secret:aura/(\w+)/", "Secrets Manager ARN"),
            (r"ssm.*parameter.*aura/(\w+)/", "SSM parameter"),
        ]

        for pattern, pattern_name in secret_patterns:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                detected_env = match.group(1).lower()
                if (
                    detected_env in ["dev", "qa", "staging", "prod"]
                    and detected_env != self.target_env
                ):
                    violations.append(
                        Violation(
                            rule_id="ENV-102",
                            severity=Severity.WARNING,
                            resource_type=resource.kind,
                            resource_name=resource.name,
                            field_path=f"data.{key}",
                            expected_value=f"{pattern_name} with /{self.target_env}/",
                            actual_value=value,
                            message=f"Secret reference uses {detected_env} path instead of {self.target_env}",
                            suggested_fix=f"Update path to use /{self.target_env}/",
                            auto_remediable=False,
                        )
                    )

        return violations

    def _check_sns_sqs(
        self, resource: ManifestResource, key: str, value: str
    ) -> list[Violation]:
        """Check ENV-005: SNS/SQS ARNs must reference correct account."""
        violations = []

        # Look for SNS/SQS ARNs or queue URLs
        is_sns_sqs = (
            "SNS" in key.upper()
            or "SQS" in key.upper()
            or "TOPIC" in key.upper()
            or "QUEUE" in key.upper()
            or "arn:aws:sns:" in value
            or "arn:aws:sqs:" in value
            or "sqs.amazonaws.com" in value
        )

        if not is_sns_sqs:
            return violations

        # Check for wrong environment in the value
        detected_env = detect_environment_in_string(value)
        if detected_env and detected_env != self.target_env:
            violations.append(
                Violation(
                    rule_id="ENV-005",
                    severity=Severity.CRITICAL,
                    resource_type=resource.kind,
                    resource_name=resource.name,
                    field_path=f"data.{key}",
                    expected_value=f"SNS/SQS resource for {self.target_env}",
                    actual_value=value,
                    message=f"SNS/SQS reference '{value}' appears to be for {detected_env}, not {self.target_env}",
                    suggested_fix=f"Use SNS/SQS resource for {self.target_env}",
                    auto_remediable=False,
                )
            )

        # Also check account ID if it's an ARN
        if "arn:aws:" in value:
            arn_parts = value.split(":")
            if len(arn_parts) >= 5:
                account_id = arn_parts[4]
                if account_id and account_id != self.env_config.account_id:
                    detected = self.registry.detect_environment_from_account(account_id)
                    env_hint = f" ({detected})" if detected else ""
                    violations.append(
                        Violation(
                            rule_id="ENV-005",
                            severity=Severity.CRITICAL,
                            resource_type=resource.kind,
                            resource_name=resource.name,
                            field_path=f"data.{key}",
                            expected_value=self.env_config.account_id,
                            actual_value=account_id,
                            message=f"SNS/SQS ARN references account {account_id}{env_hint} instead of {self.env_config.account_id} ({self.target_env})",
                            suggested_fix=f"Use account {self.env_config.account_id}",
                            auto_remediable=False,
                        )
                    )

        return violations
