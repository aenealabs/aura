"""Remediation strategies for Environment Validator (ADR-062 Phase 4).

Concrete implementations of remediation strategies for different
violation types with safety controls.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from src.services.env_validator.models import Violation
from src.services.env_validator.remediation_engine import RemediationRisk

logger = logging.getLogger(__name__)


class BaseRemediationStrategy(ABC):
    """Base class for remediation strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy identifier."""

    @property
    @abstractmethod
    def supported_rules(self) -> list[str]:
        """List of rule IDs this strategy can remediate."""

    @abstractmethod
    def can_remediate(self, violation: Violation, environment: str) -> bool:
        """Check if this strategy can remediate the violation."""

    @abstractmethod
    def get_risk_level(self, violation: Violation, environment: str) -> RemediationRisk:
        """Determine the risk level of remediation."""

    @abstractmethod
    def create_patch(self, violation: Violation, environment: str) -> tuple[dict, str]:
        """Create remediation patch and description."""

    @abstractmethod
    def apply_patch(
        self,
        violation: Violation,
        patch: dict,
        environment: str,
        dry_run: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """Apply the remediation patch."""


class EnvironmentVariableStrategy(BaseRemediationStrategy):
    """Strategy for fixing ENVIRONMENT variable mismatches (ENV-101).

    This is a zero-risk fix that simply patches the ENVIRONMENT
    env var to match the target deployment environment.
    """

    @property
    def name(self) -> str:
        return "env-var-fix"

    @property
    def supported_rules(self) -> list[str]:
        return ["ENV-101"]

    def can_remediate(self, violation: Violation, environment: str) -> bool:
        """ENV-101 can always be remediated."""
        if violation.rule_id != "ENV-101":
            return False

        # Must be a ConfigMap or environment variable
        if violation.resource_type not in ["ConfigMap", "Deployment", "Pod"]:
            return False

        return True

    def get_risk_level(self, violation: Violation, environment: str) -> RemediationRisk:
        """ENVIRONMENT variable fix is always safe."""
        return RemediationRisk.SAFE

    def create_patch(self, violation: Violation, environment: str) -> tuple[dict, str]:
        """Create JSON patch for ENVIRONMENT variable."""
        # Determine patch path based on resource type and field
        field_path = violation.field_path
        expected = violation.expected_value

        # Create kubectl-style strategic merge patch
        patch = {
            "op": "replace",
            "path": self._convert_to_json_pointer(field_path),
            "value": expected,
        }

        description = (
            f"Update {violation.resource_type}/{violation.resource_name} "
            f"field '{field_path}' from '{violation.actual_value}' to '{expected}'"
        )

        return {"patches": [patch]}, description

    def apply_patch(
        self,
        violation: Violation,
        patch: dict,
        environment: str,
        dry_run: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """Apply the ENVIRONMENT variable patch.

        In production, this would use kubectl or the K8s API.
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would apply patch: {patch}")
            return True, None

        # Production implementation would use:
        # kubectl patch configmap <name> --type='json' -p='[<patches>]'
        # or the K8s Python client

        logger.info(f"Applying patch to {violation.resource_name}: {patch}")

        # Placeholder for actual K8s patch implementation
        # In production, integrate with kubernetes.client
        return True, None

    @staticmethod
    def _convert_to_json_pointer(field_path: str) -> str:
        """Convert dot notation to JSON pointer format.

        Example: data.ENVIRONMENT -> /data/ENVIRONMENT
        """
        parts = field_path.replace("[", ".").replace("]", "").split(".")
        return "/" + "/".join(parts)


class ResourceNamingStrategy(BaseRemediationStrategy):
    """Strategy for fixing resource naming convention violations (ENV-201).

    Low-risk fix that updates resource names to follow naming conventions.
    Auto-remediate in dev/qa only; HITL required in staging/prod.
    """

    @property
    def name(self) -> str:
        return "naming-fix"

    @property
    def supported_rules(self) -> list[str]:
        return ["ENV-201"]

    def can_remediate(self, violation: Violation, environment: str) -> bool:
        """Can remediate naming issues in dev/qa."""
        if violation.rule_id != "ENV-201":
            return False

        # Only auto-remediate in dev/qa
        return environment in ["dev", "qa"]

    def get_risk_level(self, violation: Violation, environment: str) -> RemediationRisk:
        """Naming fix is low risk in dev/qa."""
        if environment in ["dev", "qa"]:
            return RemediationRisk.LOW
        return RemediationRisk.MEDIUM

    def create_patch(self, violation: Violation, environment: str) -> tuple[dict, str]:
        """Create patch for resource naming."""
        field_path = violation.field_path
        expected = violation.expected_value
        actual = violation.actual_value

        patch = {
            "op": "replace",
            "path": self._convert_to_json_pointer(field_path),
            "value": expected,
        }

        description = (
            f"Update {violation.resource_type}/{violation.resource_name} "
            f"naming from '{actual}' to '{expected}' to follow convention"
        )

        return {"patches": [patch]}, description

    def apply_patch(
        self,
        violation: Violation,
        patch: dict,
        environment: str,
        dry_run: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """Apply naming fix patch."""
        if dry_run:
            logger.info(f"[DRY RUN] Would apply naming patch: {patch}")
            return True, None

        # Note: Renaming K8s resources often requires delete + recreate
        # This is a simplified version
        logger.info(f"Applying naming patch to {violation.resource_name}: {patch}")
        return True, None

    @staticmethod
    def _convert_to_json_pointer(field_path: str) -> str:
        """Convert dot notation to JSON pointer format."""
        parts = field_path.replace("[", ".").replace("]", "").split(".")
        return "/" + "/".join(parts)


class TagConsistencyStrategy(BaseRemediationStrategy):
    """Strategy for fixing tag consistency violations (ENV-202).

    Low-risk fix that adds/updates resource tags.
    Auto-remediate in dev/qa only.
    """

    @property
    def name(self) -> str:
        return "tag-fix"

    @property
    def supported_rules(self) -> list[str]:
        return ["ENV-202"]

    def can_remediate(self, violation: Violation, environment: str) -> bool:
        """Can remediate tag issues in dev/qa."""
        if violation.rule_id != "ENV-202":
            return False

        return environment in ["dev", "qa"]

    def get_risk_level(self, violation: Violation, environment: str) -> RemediationRisk:
        """Tag fix is low risk."""
        if environment in ["dev", "qa"]:
            return RemediationRisk.LOW
        return RemediationRisk.MEDIUM

    def create_patch(self, violation: Violation, environment: str) -> tuple[dict, str]:
        """Create patch for tag update."""
        expected = violation.expected_value
        actual = violation.actual_value

        # Tags are typically in metadata.labels or metadata.annotations
        patch = {
            "op": "replace" if actual else "add",
            "path": self._convert_to_json_pointer(violation.field_path),
            "value": expected,
        }

        operation = "Update" if actual else "Add"
        description = (
            f"{operation} tag on {violation.resource_type}/{violation.resource_name}: "
            f"'{violation.field_path}' = '{expected}'"
        )

        return {"patches": [patch]}, description

    def apply_patch(
        self,
        violation: Violation,
        patch: dict,
        environment: str,
        dry_run: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """Apply tag patch."""
        if dry_run:
            logger.info(f"[DRY RUN] Would apply tag patch: {patch}")
            return True, None

        logger.info(f"Applying tag patch to {violation.resource_name}: {patch}")
        return True, None

    @staticmethod
    def _convert_to_json_pointer(field_path: str) -> str:
        """Convert dot notation to JSON pointer format."""
        parts = field_path.replace("[", ".").replace("]", "").split(".")
        return "/" + "/".join(parts)


class ConfigMapValueStrategy(BaseRemediationStrategy):
    """Strategy for fixing ConfigMap value mismatches.

    Medium-risk fix that updates ConfigMap data values.
    Auto-remediate in dev/qa only; HITL required in staging/prod.

    Note: This handles ConfigMap values that are NOT covered by
    EnvironmentVariableStrategy (which handles ENVIRONMENT vars).
    """

    @property
    def name(self) -> str:
        return "configmap-value-fix"

    @property
    def supported_rules(self) -> list[str]:
        # Note: ENV-101 is handled by EnvironmentVariableStrategy
        # This strategy handles other ConfigMap-specific values
        return []  # General strategy, not rule-specific

    def can_remediate(self, violation: Violation, environment: str) -> bool:
        """Can remediate ConfigMap values in dev/qa."""
        if violation.resource_type != "ConfigMap":
            return False

        # Only non-sensitive ConfigMap values
        sensitive_patterns = [
            "password",
            "secret",
            "token",
            "key",
            "credential",
            "arn:",
            "account_id",
            "role-arn",
        ]

        field_lower = violation.field_path.lower()
        value_lower = str(violation.actual_value).lower()

        for pattern in sensitive_patterns:
            if pattern in field_lower or pattern in value_lower:
                return False

        return environment in ["dev", "qa"]

    def get_risk_level(self, violation: Violation, environment: str) -> RemediationRisk:
        """ConfigMap value fix risk depends on environment."""
        if environment in ["dev", "qa"]:
            return RemediationRisk.LOW
        return RemediationRisk.MEDIUM

    def create_patch(self, violation: Violation, environment: str) -> tuple[dict, str]:
        """Create patch for ConfigMap value."""
        field_path = violation.field_path
        expected = violation.expected_value

        patch = {
            "op": "replace",
            "path": self._convert_to_json_pointer(field_path),
            "value": expected,
        }

        description = (
            f"Update ConfigMap/{violation.resource_name} "
            f"'{field_path}' from '{violation.actual_value}' to '{expected}'"
        )

        return {"patches": [patch]}, description

    def apply_patch(
        self,
        violation: Violation,
        patch: dict,
        environment: str,
        dry_run: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """Apply ConfigMap value patch."""
        if dry_run:
            logger.info(f"[DRY RUN] Would apply ConfigMap patch: {patch}")
            return True, None

        logger.info(f"Applying ConfigMap patch to {violation.resource_name}: {patch}")
        return True, None

    @staticmethod
    def _convert_to_json_pointer(field_path: str) -> str:
        """Convert dot notation to JSON pointer format."""
        parts = field_path.replace("[", ".").replace("]", "").split(".")
        return "/" + "/".join(parts)


class HITLOnlyStrategy(BaseRemediationStrategy):
    """Strategy for violations that require HITL approval (security-critical).

    This strategy creates remediation actions but never auto-executes them.
    All actions require human approval through the approval workflow.
    """

    # Security-critical rules that require HITL
    CRITICAL_RULES = [
        "ENV-001",  # Account ID
        "ENV-002",  # ECR registry
        "ENV-003",  # DynamoDB tables
        "ENV-004",  # Neptune/OpenSearch endpoints
        "ENV-005",  # SNS/SQS ARNs
        "ENV-006",  # Region
        "ENV-007",  # KMS keys
        "ENV-008",  # IAM roles
        "ENV-102",  # Secret paths
        "ENV-103",  # Log groups
        "ENV-104",  # IRSA annotations
    ]

    @property
    def name(self) -> str:
        return "hitl-only"

    @property
    def supported_rules(self) -> list[str]:
        return self.CRITICAL_RULES

    def can_remediate(self, violation: Violation, environment: str) -> bool:
        """HITL strategies can always propose a remediation (with approval)."""
        return violation.rule_id in self.CRITICAL_RULES

    def get_risk_level(self, violation: Violation, environment: str) -> RemediationRisk:
        """All HITL violations are critical risk."""
        return RemediationRisk.CRITICAL

    def create_patch(self, violation: Violation, environment: str) -> tuple[dict, str]:
        """Create proposed patch for HITL review."""
        field_path = violation.field_path
        expected = violation.expected_value
        actual = violation.actual_value

        patch = {
            "op": "replace",
            "path": self._convert_to_json_pointer(field_path),
            "value": expected,
            "requires_approval": True,
            "risk_reason": self._get_risk_reason(violation.rule_id),
        }

        description = (
            f"[REQUIRES APPROVAL] Update {violation.resource_type}/"
            f"{violation.resource_name} field '{field_path}' "
            f"from '{actual}' to '{expected}'. "
            f"Reason: {self._get_risk_reason(violation.rule_id)}"
        )

        return {"patches": [patch]}, description

    def apply_patch(
        self,
        violation: Violation,
        patch: dict,
        environment: str,
        dry_run: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """Apply patch (only after HITL approval)."""
        if dry_run:
            logger.info(f"[DRY RUN] HITL patch (would require approval): {patch}")
            return True, None

        # In production, verify that proper approval was obtained
        # before applying security-critical changes
        logger.warning(f"Applying security-critical patch to {violation.resource_name}")
        return True, None

    @staticmethod
    def _convert_to_json_pointer(field_path: str) -> str:
        """Convert dot notation to JSON pointer format."""
        parts = field_path.replace("[", ".").replace("]", "").split(".")
        return "/" + "/".join(parts)

    @staticmethod
    def _get_risk_reason(rule_id: str) -> str:
        """Get human-readable risk reason for a rule."""
        reasons = {
            "ENV-001": "Account ID changes require cross-account validation",
            "ENV-002": "ECR registry change could deploy untested code",
            "ENV-003": "DynamoDB table change could cause data access issues",
            "ENV-004": "Database endpoint change affects data integrity",
            "ENV-005": "Messaging ARN change affects event routing",
            "ENV-006": "Region change may affect compliance (GovCloud)",
            "ENV-007": "KMS key change affects encryption chain",
            "ENV-008": "IAM role change affects service permissions",
            "ENV-102": "Secret path change requires security review",
            "ENV-103": "Log group change requires resource creation",
            "ENV-104": "IRSA annotation affects pod identity",
        }
        return reasons.get(rule_id, "Security-critical change requires review")


def get_default_strategies() -> list[BaseRemediationStrategy]:
    """Get default set of remediation strategies.

    Returns:
        List of all available strategies in priority order
    """
    return [
        EnvironmentVariableStrategy(),
        ResourceNamingStrategy(),
        TagConsistencyStrategy(),
        ConfigMapValueStrategy(),
        HITLOnlyStrategy(),  # Catch-all for critical rules
    ]


class MockRemediationStrategy(BaseRemediationStrategy):
    """Mock strategy for testing."""

    def __init__(
        self,
        name: str = "mock-strategy",
        rules: Optional[list[str]] = None,
        can_fix: bool = True,
        risk: RemediationRisk = RemediationRisk.SAFE,
    ):
        self._name = name
        self._rules = rules or ["ENV-101"]
        self._can_fix = can_fix
        self._risk = risk
        self.applied_patches: list[dict] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_rules(self) -> list[str]:
        return self._rules

    def can_remediate(self, violation: Violation, environment: str) -> bool:
        return self._can_fix and violation.rule_id in self._rules

    def get_risk_level(self, violation: Violation, environment: str) -> RemediationRisk:
        return self._risk

    def create_patch(self, violation: Violation, environment: str) -> tuple[dict, str]:
        patch = {
            "op": "replace",
            "value": violation.expected_value,
            "mock": True,
        }
        return {"patches": [patch]}, f"Mock fix for {violation.rule_id}"

    def apply_patch(
        self,
        violation: Violation,
        patch: dict,
        environment: str,
        dry_run: bool = False,
    ) -> tuple[bool, Optional[str]]:
        if not dry_run:
            self.applied_patches.append(
                {
                    "violation": violation.rule_id,
                    "patch": patch,
                    "environment": environment,
                }
            )
        return True, None
