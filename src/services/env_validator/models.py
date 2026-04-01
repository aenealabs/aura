"""Data models for Environment Validator Agent (ADR-062)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    """Violation severity levels."""

    CRITICAL = "critical"  # Block deployment
    WARNING = "warning"  # Alert but allow
    INFO = "info"  # Log only


class ValidationResult(str, Enum):
    """Overall validation result."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


class TriggerType(str, Enum):
    """What triggered the validation."""

    PRE_DEPLOY = "pre_deploy"
    POST_DEPLOY = "post_deploy"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    DRIFT_DETECTION = "drift_detection"


@dataclass
class RuleDefinition:
    """Definition of a validation rule."""

    rule_id: str
    description: str
    severity: Severity
    category: str  # e.g., "account", "ecr", "dynamodb", "naming"

    def __hash__(self) -> int:
        return hash(self.rule_id)


# Rule definitions per ADR-062
VALIDATION_RULES: dict[str, RuleDefinition] = {
    # Critical rules (block deployment)
    "ENV-001": RuleDefinition(
        rule_id="ENV-001",
        description="Account ID in ARNs must match target environment",
        severity=Severity.CRITICAL,
        category="account",
    ),
    "ENV-002": RuleDefinition(
        rule_id="ENV-002",
        description="ECR image registry must match target account",
        severity=Severity.CRITICAL,
        category="ecr",
    ),
    "ENV-003": RuleDefinition(
        rule_id="ENV-003",
        description="DynamoDB table names must contain correct env suffix",
        severity=Severity.CRITICAL,
        category="dynamodb",
    ),
    "ENV-004": RuleDefinition(
        rule_id="ENV-004",
        description="Neptune/OpenSearch endpoints must match environment",
        severity=Severity.CRITICAL,
        category="endpoint",
    ),
    "ENV-005": RuleDefinition(
        rule_id="ENV-005",
        description="SNS/SQS ARNs must reference correct account",
        severity=Severity.CRITICAL,
        category="messaging",
    ),
    "ENV-006": RuleDefinition(
        rule_id="ENV-006",
        description="Region in ARNs must match target environment",
        severity=Severity.CRITICAL,
        category="region",
    ),
    "ENV-007": RuleDefinition(
        rule_id="ENV-007",
        description="KMS key ARNs must be environment-specific",
        severity=Severity.CRITICAL,
        category="kms",
    ),
    "ENV-008": RuleDefinition(
        rule_id="ENV-008",
        description="IAM role ARNs must match target account",
        severity=Severity.CRITICAL,
        category="iam",
    ),
    # Warning rules (alert but allow)
    "ENV-101": RuleDefinition(
        rule_id="ENV-101",
        description="ENVIRONMENT variable should match deployment target",
        severity=Severity.WARNING,
        category="env_var",
    ),
    "ENV-102": RuleDefinition(
        rule_id="ENV-102",
        description="Secret references should use environment-specific paths",
        severity=Severity.WARNING,
        category="secrets",
    ),
    "ENV-103": RuleDefinition(
        rule_id="ENV-103",
        description="Log group names should contain environment suffix",
        severity=Severity.WARNING,
        category="logging",
    ),
    "ENV-104": RuleDefinition(
        rule_id="ENV-104",
        description="Service account annotations should match account",
        severity=Severity.WARNING,
        category="irsa",
    ),
    # Informational rules (log only)
    "ENV-201": RuleDefinition(
        rule_id="ENV-201",
        description="Resource naming convention compliance",
        severity=Severity.INFO,
        category="naming",
    ),
    "ENV-202": RuleDefinition(
        rule_id="ENV-202",
        description="Tag consistency",
        severity=Severity.INFO,
        category="tagging",
    ),
}


@dataclass
class Violation:
    """A single validation violation."""

    rule_id: str
    severity: Severity
    resource_type: str
    resource_name: str
    field_path: str
    expected_value: str
    actual_value: str
    message: str
    suggested_fix: Optional[str] = None
    auto_remediable: bool = False

    @property
    def rule(self) -> RuleDefinition:
        """Get the rule definition for this violation."""
        return VALIDATION_RULES.get(
            self.rule_id,
            RuleDefinition(
                rule_id=self.rule_id,
                description="Unknown rule",
                severity=self.severity,
                category="unknown",
            ),
        )


@dataclass
class ValidationRun:
    """Result of a complete validation run."""

    run_id: str
    timestamp: datetime
    environment: str
    trigger: TriggerType
    manifest_hash: Optional[str]
    duration_ms: int
    result: ValidationResult
    violations: list[Violation] = field(default_factory=list)
    warnings: list[Violation] = field(default_factory=list)
    info: list[Violation] = field(default_factory=list)
    resources_scanned: int = 0

    @property
    def has_critical(self) -> bool:
        """Check if there are any critical violations."""
        return any(v.severity == Severity.CRITICAL for v in self.violations)

    @property
    def violation_count(self) -> int:
        """Total number of violations across all severities."""
        return len(self.violations) + len(self.warnings) + len(self.info)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "environment": self.environment,
            "trigger": self.trigger.value,
            "manifest_hash": self.manifest_hash,
            "duration_ms": self.duration_ms,
            "result": self.result.value,
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity.value,
                    "resource_type": v.resource_type,
                    "resource_name": v.resource_name,
                    "field_path": v.field_path,
                    "expected_value": v.expected_value,
                    "actual_value": v.actual_value,
                    "message": v.message,
                    "suggested_fix": v.suggested_fix,
                    "auto_remediable": v.auto_remediable,
                }
                for v in self.violations
            ],
            "warnings": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity.value,
                    "resource_type": v.resource_type,
                    "resource_name": v.resource_name,
                    "message": v.message,
                }
                for v in self.warnings
            ],
            "info": [
                {
                    "rule_id": v.rule_id,
                    "resource_type": v.resource_type,
                    "resource_name": v.resource_name,
                    "message": v.message,
                }
                for v in self.info
            ],
            "resources_scanned": self.resources_scanned,
            "has_critical": self.has_critical,
            "violation_count": self.violation_count,
        }


@dataclass
class EnvironmentConfig:
    """Configuration for a single environment."""

    account_id: str
    ecr_registry: str
    neptune_cluster: str
    opensearch_domain: str
    resource_suffix: str
    eks_cluster: str
    region: str

    def matches_account(self, arn: str) -> bool:
        """Check if an ARN belongs to this environment's account."""
        return f":{self.account_id}:" in arn

    def matches_region(self, arn: str) -> bool:
        """Check if an ARN is in this environment's region."""
        return f":{self.region}:" in arn

    def matches_suffix(self, resource_name: str) -> bool:
        """Check if a resource name has the correct environment suffix."""
        return resource_name.endswith(self.resource_suffix)


@dataclass
class EnvironmentRegistry:
    """Registry of all environment configurations."""

    environments: dict[str, EnvironmentConfig] = field(default_factory=dict)

    def get(self, env: str) -> Optional[EnvironmentConfig]:
        """Get configuration for an environment."""
        return self.environments.get(env)

    def get_other_environments(self, current_env: str) -> list[str]:
        """Get list of other environment names (for cross-env detection)."""
        return [e for e in self.environments.keys() if e != current_env]

    def detect_environment_from_account(self, account_id: str) -> Optional[str]:
        """Detect which environment an account ID belongs to."""
        for env_name, config in self.environments.items():
            if config.account_id == account_id:
                return env_name
        return None


@dataclass
class ManifestResource:
    """A Kubernetes resource from a manifest."""

    api_version: str
    kind: str
    name: str
    namespace: Optional[str]
    raw: dict  # Original YAML content

    @property
    def full_name(self) -> str:
        """Full resource identifier."""
        ns = self.namespace or "default"
        return f"{self.kind}/{ns}/{self.name}"
