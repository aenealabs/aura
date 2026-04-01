"""
Project Aura - Policy Validator

Validates capability policies before deployment.
Implements ADR-070 for Policy-as-Code with GitOps.

Validation Checks:
1. Schema compliance
2. Reference integrity (all tools exist)
3. No circular inheritance
4. No privilege escalation paths
5. No toxic capability combinations
6. Compliance requirements met
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .contracts import ToolClassification
from .graph_contracts import (
    ConflictType,
    CoverageGap,
    EscalationPath,
    RiskLevel,
    ToxicCombination,
)
from .policy import AgentCapabilityPolicy
from .registry import CapabilityRegistry, get_capability_registry

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    """Represents a validation error."""

    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    location: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "location": self.location,
            "details": self.details,
        }


@dataclass
class ValidationWarning:
    """Represents a validation warning."""

    code: str
    message: str
    recommendation: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "recommendation": self.recommendation,
            "details": self.details,
        }


@dataclass
class ValidationContext:
    """Context for policy validation."""

    environment: str = "development"
    strict_mode: bool = False
    compliance_requirements: list[str] = field(default_factory=list)
    existing_policies: list[AgentCapabilityPolicy] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of policy validation."""

    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationWarning] = field(default_factory=list)
    escalation_paths: list[EscalationPath] = field(default_factory=list)
    coverage_gaps: list[CoverageGap] = field(default_factory=list)
    toxic_combinations: list[ToxicCombination] = field(default_factory=list)
    validation_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "escalation_paths": [p.to_dict() for p in self.escalation_paths],
            "coverage_gaps": [g.to_dict() for g in self.coverage_gaps],
            "toxic_combinations": [t.to_dict() for t in self.toxic_combinations],
            "validation_time_ms": self.validation_time_ms,
        }


class PolicyValidator:
    """
    Validates capability policies before deployment.

    Performs comprehensive validation including:
    - Schema compliance
    - Reference integrity
    - Inheritance validation
    - Privilege escalation detection
    - Toxic combination detection
    - Coverage gap analysis
    """

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
    ):
        """
        Initialize the policy validator.

        Args:
            registry: Capability registry for tool lookups
        """
        self.registry = registry or get_capability_registry()

        # Define toxic capability combinations
        self._toxic_combinations: list[tuple[str, str, str]] = [
            ("access_secrets", "execute_code", "Can leak secrets via code execution"),
            ("modify_iam_policy", "execute_code", "Can escalate privileges via code"),
            (
                "provision_sandbox",
                "destroy_sandbox",
                "Can create and destroy resources",
            ),
            ("deploy_to_production", "modify_iam_policy", "Full production control"),
        ]

        # Define compliance requirements mapping
        self._compliance_requirements: dict[str, list[str]] = {
            "cmmc-l3": ["audit_logging", "least_privilege", "separation_of_duties"],
            "sox": [
                "audit_logging",
                "change_management",
                "access_control",
                "separation_of_duties",
            ],
            "nist-800-53": ["audit_logging", "least_privilege", "mfa_enforcement"],
        }

    async def validate_policy(
        self,
        policy: AgentCapabilityPolicy,
        context: ValidationContext | None = None,
    ) -> ValidationResult:
        """
        Comprehensive policy validation.

        Args:
            policy: Policy to validate
            context: Validation context

        Returns:
            ValidationResult with errors, warnings, and analysis
        """
        import time

        start_time = time.time()
        context = context or ValidationContext()
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []

        # Schema validation
        schema_errors = self._validate_schema(policy)
        errors.extend(schema_errors)

        # Reference integrity
        ref_errors = await self._validate_references(policy)
        errors.extend(ref_errors)

        # Inheritance validation
        inheritance_errors = await self._validate_inheritance(policy, context)
        errors.extend(inheritance_errors)

        # Privilege escalation detection
        escalation_paths = await self._detect_escalation_paths(policy)
        if escalation_paths:
            errors.append(
                ValidationError(
                    code="PRIVILEGE_ESCALATION",
                    message=f"Found {len(escalation_paths)} privilege escalation paths",
                    details={"paths": [p.to_dict() for p in escalation_paths]},
                )
            )

        # Toxic combinations
        toxic_combinations = await self._detect_toxic_combinations(policy)
        for combo in toxic_combinations:
            errors.append(
                ValidationError(
                    code="TOXIC_COMBINATION",
                    message=f"Toxic combination: {combo.capability_a} + {combo.capability_b}",
                    details={"reason": combo.description},
                )
            )

        # Coverage gaps
        coverage_gaps = await self._detect_coverage_gaps(policy)
        for gap in coverage_gaps:
            warnings.append(
                ValidationWarning(
                    code="COVERAGE_GAP",
                    message=f"{gap.gap_type}: Agent {gap.agent_name} has dangerous capabilities without required monitoring",
                    recommendation=gap.recommendation,
                )
            )

        # Compliance validation
        if context.compliance_requirements:
            compliance_errors = self._validate_compliance(
                policy, context.compliance_requirements
            )
            errors.extend(compliance_errors)

        # Rate limit validation
        rate_warnings = self._validate_rate_limits(policy)
        warnings.extend(rate_warnings)

        validation_time = (time.time() - start_time) * 1000

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            escalation_paths=escalation_paths,
            coverage_gaps=coverage_gaps,
            toxic_combinations=toxic_combinations,
            validation_time_ms=validation_time,
        )

    def _validate_schema(self, policy: AgentCapabilityPolicy) -> list[ValidationError]:
        """Validate policy schema."""
        errors: list[ValidationError] = []

        # Check required fields
        if not policy.agent_type:
            errors.append(
                ValidationError(
                    code="MISSING_FIELD",
                    message="agent_type is required",
                    location="agent_type",
                )
            )

        # Check policy version format
        if not policy.version:
            errors.append(
                ValidationError(
                    code="MISSING_FIELD",
                    message="version is required",
                    location="version",
                )
            )

        # Check allowed tools structure (dict[str, list[str]])
        if policy.allowed_tools:
            for tool_name, actions in policy.allowed_tools.items():
                if not isinstance(tool_name, str):
                    errors.append(
                        ValidationError(
                            code="INVALID_TOOL_FORMAT",
                            message=f"Tool name must be string, got {type(tool_name).__name__}",
                            location="allowed_tools",
                        )
                    )
                if not isinstance(actions, list):
                    errors.append(
                        ValidationError(
                            code="INVALID_TOOL_FORMAT",
                            message=f"Actions must be list, got {type(actions).__name__}",
                            location=f"allowed_tools/{tool_name}",
                        )
                    )

        # Check denied tools structure
        if policy.denied_tools:
            for tool in policy.denied_tools:
                if not isinstance(tool, str):
                    errors.append(
                        ValidationError(
                            code="INVALID_TOOL_FORMAT",
                            message=f"Tool must be string, got {type(tool).__name__}",
                            location="denied_tools",
                        )
                    )

        return errors

    async def _validate_references(
        self, policy: AgentCapabilityPolicy
    ) -> list[ValidationError]:
        """Validate that all referenced tools exist."""
        errors: list[ValidationError] = []

        # allowed_tools is dict[str, list[str]], get the keys
        allowed_tool_names = (
            set(policy.allowed_tools.keys()) if policy.allowed_tools else set()
        )
        all_tools = allowed_tool_names | set(policy.denied_tools or [])

        for tool_name in all_tools:
            if not self.registry.get_tool(tool_name):
                errors.append(
                    ValidationError(
                        code="UNKNOWN_TOOL",
                        message=f"Tool '{tool_name}' not found in registry",
                        location=f"tools/{tool_name}",
                        details={"tool_name": tool_name},
                    )
                )

        return errors

    async def _validate_inheritance(
        self,
        policy: AgentCapabilityPolicy,
        context: ValidationContext,
    ) -> list[ValidationError]:
        """Validate inheritance chain for circular references."""
        errors: list[ValidationError] = []

        if not policy.parent_policy:
            return errors

        # Check for circular inheritance
        visited: set[str] = set()
        current = policy.agent_type
        parent = policy.parent_policy

        if parent in visited:
            errors.append(
                ValidationError(
                    code="CIRCULAR_INHERITANCE",
                    message=f"Circular inheritance detected: {current} -> {parent}",
                    location="parent_policy",
                    details={"chain": list(visited)},
                )
            )
        else:
            visited.add(parent)

            # Check parent exists
            parent_policy_obj = next(
                (p for p in context.existing_policies if p.agent_type == parent), None
            )
            if not parent_policy_obj:
                errors.append(
                    ValidationError(
                        code="MISSING_PARENT",
                        message=f"Parent policy '{parent}' not found",
                        location="parent_policy",
                    )
                )

        return errors

    async def _detect_escalation_paths(
        self, policy: AgentCapabilityPolicy
    ) -> list[EscalationPath]:
        """Detect privilege escalation paths in policy."""
        escalation_paths: list[EscalationPath] = []

        # allowed_tools is dict[str, list[str]], get the keys
        allowed_tools = (
            set(policy.allowed_tools.keys()) if policy.allowed_tools else set()
        )

        # Check for known escalation patterns
        escalation_patterns = [
            (["modify_iam_policy"], "Can modify IAM to grant self more permissions"),
            (["access_secrets", "execute_code"], "Can exfiltrate secrets via code"),
            (
                ["provision_sandbox", "deploy_to_production"],
                "Can deploy sandbox code to production",
            ),
        ]

        import uuid

        for required_tools, description in escalation_patterns:
            if all(tool in allowed_tools for tool in required_tools):
                escalation_paths.append(
                    EscalationPath(
                        path_id=f"esc-{uuid.uuid4().hex[:8]}",
                        source_agent=policy.agent_type,
                        target_capability=required_tools[0],
                        classification=ToolClassification.CRITICAL,
                        path=(policy.agent_type,),
                        risk_score=0.9,
                        risk_level=RiskLevel.HIGH,
                        description=description,
                        mitigation_suggestion="Separate these capabilities into different agents",
                    )
                )

        return escalation_paths

    async def _detect_toxic_combinations(
        self, policy: AgentCapabilityPolicy
    ) -> list[ToxicCombination]:
        """Detect toxic capability combinations."""
        toxic_found: list[ToxicCombination] = []

        # allowed_tools is dict[str, list[str]], get the keys
        allowed_tools = (
            set(policy.allowed_tools.keys()) if policy.allowed_tools else set()
        )

        import uuid

        for cap_a, cap_b, risk_desc in self._toxic_combinations:
            if cap_a in allowed_tools and cap_b in allowed_tools:
                toxic_found.append(
                    ToxicCombination(
                        combination_id=f"toxic-{uuid.uuid4().hex[:8]}",
                        agent_name=policy.agent_type,
                        capability_a=cap_a,
                        capability_b=cap_b,
                        conflict_type=ConflictType.PRIVILEGE_ESCALATION,
                        severity=RiskLevel.HIGH,
                        policy_reference="ADR-066",
                        description=risk_desc,
                        remediation="Separate these capabilities into different agents",
                    )
                )

        return toxic_found

    async def _detect_coverage_gaps(
        self, policy: AgentCapabilityPolicy
    ) -> list[CoverageGap]:
        """Detect coverage gaps in policy."""
        gaps: list[CoverageGap] = []

        # allowed_tools is dict[str, list[str]], get the keys
        allowed_tools = (
            set(policy.allowed_tools.keys()) if policy.allowed_tools else set()
        )

        # Check for DANGEROUS without MONITORING
        dangerous_tools = [
            t
            for t in allowed_tools
            if self.registry.get_tool(t)
            and self.registry.get_tool(t).classification == ToolClassification.DANGEROUS
        ]

        monitoring_tools = [
            t
            for t in allowed_tools
            if self.registry.get_tool(t)
            and self.registry.get_tool(t).classification
            == ToolClassification.MONITORING
        ]

        import uuid

        if dangerous_tools and not monitoring_tools:
            gaps.append(
                CoverageGap(
                    gap_id=f"gap-{uuid.uuid4().hex[:8]}",
                    agent_name=policy.agent_type,
                    agent_type=policy.agent_type,
                    dangerous_capabilities=tuple(dangerous_tools),
                    missing_capabilities=("query_audit_logs", "get_agent_metrics"),
                    gap_type="missing_monitoring",
                    risk_level=RiskLevel.MEDIUM,
                    recommendation="Add monitoring capabilities to track dangerous operations",
                )
            )

        # Check for production access without approval requirements
        production_tools = ["deploy_to_production", "modify_production_data"]
        has_production = any(t in allowed_tools for t in production_tools)

        if has_production and not policy.constraints:
            gaps.append(
                CoverageGap(
                    gap_id=f"gap-{uuid.uuid4().hex[:8]}",
                    agent_name=policy.agent_type,
                    agent_type=policy.agent_type,
                    dangerous_capabilities=tuple(
                        t for t in production_tools if t in allowed_tools
                    ),
                    missing_capabilities=("hitl_approval", "context_constraint"),
                    gap_type="missing_approval",
                    risk_level=RiskLevel.HIGH,
                    recommendation="Add approval requirements for production operations",
                )
            )

        return gaps

    def _validate_compliance(
        self, policy: AgentCapabilityPolicy, requirements: list[str]
    ) -> list[ValidationError]:
        """Validate policy against compliance requirements."""
        errors: list[ValidationError] = []

        for req in requirements:
            if req not in self._compliance_requirements:
                continue

            checks = self._compliance_requirements[req]

            # Least privilege check
            if "least_privilege" in checks:
                # allowed_tools is dict[str, list[str]], get the keys
                tool_names = (
                    list(policy.allowed_tools.keys()) if policy.allowed_tools else []
                )
                critical_tools = [
                    t
                    for t in tool_names
                    if self.registry.get_tool(t)
                    and self.registry.get_tool(t).classification
                    == ToolClassification.CRITICAL
                ]
                if critical_tools:
                    errors.append(
                        ValidationError(
                            code="COMPLIANCE_VIOLATION",
                            message=f"Least privilege ({req}): CRITICAL tools should require escalation",
                            details={"tools": critical_tools, "requirement": req},
                        )
                    )

            # Separation of duties check
            if "separation_of_duties" in checks:
                tool_names = (
                    set(policy.allowed_tools.keys()) if policy.allowed_tools else set()
                )
                if "approve_patch" in tool_names and "create_patch" in tool_names:
                    errors.append(
                        ValidationError(
                            code="COMPLIANCE_VIOLATION",
                            message=f"Separation of duties ({req}): Cannot both create and approve patches",
                            details={"requirement": req},
                        )
                    )

        return errors

    def _validate_rate_limits(
        self, policy: AgentCapabilityPolicy
    ) -> list[ValidationWarning]:
        """Validate rate limits configuration."""
        warnings: list[ValidationWarning] = []

        # Check if dangerous tools have rate limits
        if policy.allowed_tools:
            # allowed_tools is dict[str, list[str]], get the keys
            tool_names = list(policy.allowed_tools.keys())
            dangerous_tools = [
                t
                for t in tool_names
                if self.registry.get_tool(t)
                and self.registry.get_tool(t).classification
                in [ToolClassification.DANGEROUS, ToolClassification.CRITICAL]
            ]

            # Check if tool-specific rate limits exist for dangerous tools
            has_tool_limits = policy.tool_rate_limits and any(
                t in policy.tool_rate_limits for t in dangerous_tools
            )
            if dangerous_tools and not has_tool_limits:
                warnings.append(
                    ValidationWarning(
                        code="MISSING_RATE_LIMITS",
                        message="DANGEROUS/CRITICAL tools should have rate limits",
                        recommendation="Add rate_limits configuration for dangerous operations",
                        details={"tools": dangerous_tools},
                    )
                )

        return warnings


# Singleton instance
_validator_instance: PolicyValidator | None = None


def get_policy_validator() -> PolicyValidator:
    """Get or create the singleton policy validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = PolicyValidator()
    return _validator_instance


def reset_policy_validator() -> None:
    """Reset the singleton instance (for testing)."""
    global _validator_instance
    _validator_instance = None
