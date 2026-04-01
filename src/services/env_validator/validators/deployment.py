"""Deployment validation for Environment Validator (ADR-062).

Validates Deployment, StatefulSet, DaemonSet, and Job resources
to ensure container images come from the correct ECR registry.

Rules implemented:
- ENV-002: ECR image registry must match target account
- ENV-104: Service account annotations should match account
"""

import re
from typing import Optional

from src.services.env_validator.config import load_environment_registry
from src.services.env_validator.models import ManifestResource, Severity, Violation

# ECR image pattern: {account}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}
ECR_IMAGE_PATTERN = re.compile(
    r"(\d{12})\.dkr\.ecr\.([\w-]+)\.amazonaws\.com/([^:]+):?(.*)?"
)


class DeploymentValidator:
    """Validates Deployment-like resources for environment consistency."""

    # Resource kinds that have pod templates with containers
    WORKLOAD_KINDS = {
        "Deployment",
        "StatefulSet",
        "DaemonSet",
        "Job",
        "CronJob",
        "ReplicaSet",
    }

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
        """Validate a workload resource.

        Args:
            resource: Kubernetes workload resource

        Returns:
            List of violations found
        """
        violations = []

        # Check container images in workloads
        if resource.kind in self.WORKLOAD_KINDS:
            violations.extend(self._check_container_images(resource))

        # Check service account for IRSA annotations
        if resource.kind == "ServiceAccount":
            violations.extend(self._check_service_account(resource))

        return violations

    def _check_container_images(self, resource: ManifestResource) -> list[Violation]:
        """Check ENV-002: Container images must come from correct ECR."""
        violations = []

        # Get containers from pod template spec
        containers = self._get_containers(resource)

        for container_path, container in containers:
            image = container.get("image", "")
            if not image:
                continue

            match = ECR_IMAGE_PATTERN.match(image)
            if match:
                account_id = match.group(1)
                region = match.group(2)
                repo = match.group(3)

                # Check account ID
                if account_id != self.env_config.account_id:
                    detected_env = self.registry.detect_environment_from_account(
                        account_id
                    )
                    env_hint = f" ({detected_env})" if detected_env else ""

                    violations.append(
                        Violation(
                            rule_id="ENV-002",
                            severity=Severity.CRITICAL,
                            resource_type=resource.kind,
                            resource_name=resource.name,
                            field_path=f"{container_path}.image",
                            expected_value=self.env_config.ecr_registry,
                            actual_value=f"{account_id}.dkr.ecr.{region}.amazonaws.com",
                            message=f"Container image from ECR account {account_id}{env_hint}, expected {self.env_config.account_id} ({self.target_env})",
                            suggested_fix=f"Use image from {self.env_config.ecr_registry}/{repo}",
                            auto_remediable=False,  # Risky - could deploy untested code
                        )
                    )

                # Also check region
                if region != self.env_config.region:
                    violations.append(
                        Violation(
                            rule_id="ENV-002",
                            severity=Severity.CRITICAL,
                            resource_type=resource.kind,
                            resource_name=resource.name,
                            field_path=f"{container_path}.image",
                            expected_value=self.env_config.region,
                            actual_value=region,
                            message=f"Container image from ECR region {region}, expected {self.env_config.region}",
                            suggested_fix=f"Use image from {self.env_config.ecr_registry}",
                            auto_remediable=False,
                        )
                    )

        return violations

    def _get_containers(self, resource: ManifestResource) -> list[tuple[str, dict]]:
        """Extract all containers from a workload resource.

        Returns list of (path, container_dict) tuples.
        """
        containers = []

        # Different paths based on resource kind
        if resource.kind == "CronJob":
            spec_path = "spec.jobTemplate.spec.template.spec"
        elif resource.kind == "Job":
            spec_path = "spec.template.spec"
        else:
            spec_path = "spec.template.spec"

        # Navigate to pod spec
        pod_spec = self._get_nested(resource.raw, spec_path)
        if not pod_spec:
            return containers

        # Get regular containers
        for i, container in enumerate(pod_spec.get("containers", [])):
            containers.append((f"{spec_path}.containers[{i}]", container))

        # Get init containers
        for i, container in enumerate(pod_spec.get("initContainers", [])):
            containers.append((f"{spec_path}.initContainers[{i}]", container))

        return containers

    def _check_service_account(self, resource: ManifestResource) -> list[Violation]:
        """Check ENV-104: Service account IRSA annotations should match account."""
        violations = []

        annotations = resource.raw.get("metadata", {}).get("annotations", {})
        role_arn = annotations.get("eks.amazonaws.com/role-arn", "")

        if role_arn:
            # Parse account ID from role ARN
            arn_parts = role_arn.split(":")
            if len(arn_parts) >= 5:
                account_id = arn_parts[4]
                if account_id and account_id != self.env_config.account_id:
                    detected_env = self.registry.detect_environment_from_account(
                        account_id
                    )
                    env_hint = f" ({detected_env})" if detected_env else ""

                    violations.append(
                        Violation(
                            rule_id="ENV-104",
                            severity=Severity.WARNING,
                            resource_type=resource.kind,
                            resource_name=resource.name,
                            field_path="metadata.annotations.eks.amazonaws.com/role-arn",
                            expected_value=self.env_config.account_id,
                            actual_value=account_id,
                            message=f"IRSA role ARN references account {account_id}{env_hint} instead of {self.env_config.account_id} ({self.target_env})",
                            suggested_fix=f"Update IRSA annotation to use account {self.env_config.account_id}",
                            auto_remediable=False,
                        )
                    )

        return violations

    def _get_nested(self, data: dict, path: str) -> Optional[dict]:
        """Get a nested value from a dict using dot notation.

        Args:
            data: Dictionary to traverse
            path: Dot-separated path (e.g., "spec.template.spec")

        Returns:
            Value at path if found, None otherwise
        """
        current = data
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current if isinstance(current, dict) else None
