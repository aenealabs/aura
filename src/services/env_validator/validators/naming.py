"""Naming convention validation for Environment Validator (ADR-062).

Validates resource naming conventions and tag consistency.

Rules implemented:
- ENV-103: Log group names should contain environment suffix
- ENV-201: Resource naming convention compliance
- ENV-202: Tag consistency
"""

import re

from src.services.env_validator.config import (
    detect_environment_in_string,
    load_environment_registry,
)
from src.services.env_validator.models import ManifestResource, Severity, Violation


class NamingValidator:
    """Validates naming conventions for Kubernetes resources."""

    # Expected project prefix
    PROJECT_PREFIX = "aura-"

    # Required labels for all resources
    REQUIRED_LABELS = {"app", "environment"}

    # Recommended labels
    RECOMMENDED_LABELS = {"app.kubernetes.io/name", "app.kubernetes.io/part-of"}

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
        """Validate naming conventions for a resource.

        Args:
            resource: Kubernetes resource to validate

        Returns:
            List of violations found
        """
        violations = []

        # Check resource name prefix (ENV-201)
        violations.extend(self._check_name_prefix(resource))

        # Check label consistency (ENV-202)
        violations.extend(self._check_labels(resource))

        # Check log group references (ENV-103)
        violations.extend(self._check_log_groups(resource))

        return violations

    def _check_name_prefix(self, resource: ManifestResource) -> list[Violation]:
        """Check ENV-201: Resource names should follow naming convention."""
        violations = []

        name = resource.name
        if not name:
            return violations

        # Check for project prefix
        if not name.startswith(self.PROJECT_PREFIX):
            violations.append(
                Violation(
                    rule_id="ENV-201",
                    severity=Severity.INFO,
                    resource_type=resource.kind,
                    resource_name=name,
                    field_path="metadata.name",
                    expected_value=f"{self.PROJECT_PREFIX}*",
                    actual_value=name,
                    message=f"Resource name '{name}' does not follow naming convention (missing '{self.PROJECT_PREFIX}' prefix)",
                    suggested_fix=f"Rename to '{self.PROJECT_PREFIX}{name}'",
                    auto_remediable=False,
                )
            )

        return violations

    def _check_labels(self, resource: ManifestResource) -> list[Violation]:
        """Check ENV-202: Required labels should be present and consistent."""
        violations = []

        metadata = resource.raw.get("metadata", {})
        labels = metadata.get("labels", {})

        # Check required labels
        for required_label in self.REQUIRED_LABELS:
            if required_label not in labels:
                violations.append(
                    Violation(
                        rule_id="ENV-202",
                        severity=Severity.INFO,
                        resource_type=resource.kind,
                        resource_name=resource.name,
                        field_path="metadata.labels",
                        expected_value=f"label '{required_label}' present",
                        actual_value="missing",
                        message=f"Resource missing required label '{required_label}'",
                        suggested_fix=f"Add label '{required_label}' to metadata.labels",
                        auto_remediable=False,
                    )
                )

        # Check environment label value
        env_label = labels.get("environment", "")
        if env_label and env_label.lower() != self.target_env.lower():
            violations.append(
                Violation(
                    rule_id="ENV-202",
                    severity=Severity.INFO,
                    resource_type=resource.kind,
                    resource_name=resource.name,
                    field_path="metadata.labels.environment",
                    expected_value=self.target_env,
                    actual_value=env_label,
                    message=f"Environment label '{env_label}' does not match target environment '{self.target_env}'",
                    suggested_fix=f"Set label 'environment' to '{self.target_env}'",
                    auto_remediable=True,
                )
            )

        return violations

    def _check_log_groups(self, resource: ManifestResource) -> list[Violation]:
        """Check ENV-103: Log group names should contain environment suffix."""
        violations = []

        # Only check ConfigMaps and resources that might contain log group refs
        if resource.kind not in {"ConfigMap", "Deployment", "DaemonSet"}:
            return violations

        # Search for log group references
        log_group_refs = self._find_log_group_refs(resource.raw)

        for field_path, log_group in log_group_refs:
            detected_env = detect_environment_in_string(log_group)
            if detected_env and detected_env != self.target_env:
                violations.append(
                    Violation(
                        rule_id="ENV-103",
                        severity=Severity.WARNING,
                        resource_type=resource.kind,
                        resource_name=resource.name,
                        field_path=field_path,
                        expected_value=f"Log group for {self.target_env}",
                        actual_value=log_group,
                        message=f"Log group '{log_group}' appears to be for {detected_env}, not {self.target_env}",
                        suggested_fix=f"Use log group ending in {self.env_config.resource_suffix}",
                        auto_remediable=False,
                    )
                )
            elif not detected_env and not log_group.endswith(
                self.env_config.resource_suffix
            ):
                # Log group without environment suffix
                if "/aws/eks/" in log_group or "/aura/" in log_group:
                    violations.append(
                        Violation(
                            rule_id="ENV-103",
                            severity=Severity.WARNING,
                            resource_type=resource.kind,
                            resource_name=resource.name,
                            field_path=field_path,
                            expected_value=f"*{self.env_config.resource_suffix}",
                            actual_value=log_group,
                            message=f"Log group '{log_group}' missing environment suffix",
                            suggested_fix=f"Add {self.env_config.resource_suffix} suffix",
                            auto_remediable=False,
                        )
                    )

        return violations

    def _find_log_group_refs(self, data: dict, path: str = "") -> list[tuple[str, str]]:
        """Find log group references in a dictionary.

        Returns list of (path, log_group_name) tuples.
        """
        refs = []

        # Patterns that indicate log group references
        log_group_patterns = [
            re.compile(r"(/aws/\w+/[^\s\"']+)"),
            re.compile(r"(/aura/[^\s\"']+)"),
            re.compile(r"log[-_]?group", re.IGNORECASE),
        ]

        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key

            if isinstance(value, str):
                # Check if key suggests it's a log group
                if any(p.search(key) for p in log_group_patterns):
                    refs.append((current_path, value))
                # Check if value looks like a log group path
                elif value.startswith("/aws/") or value.startswith("/aura/"):
                    refs.append((current_path, value))
            elif isinstance(value, dict):
                refs.extend(self._find_log_group_refs(value, current_path))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        refs.extend(
                            self._find_log_group_refs(item, f"{current_path}[{i}]")
                        )

        return refs
