"""
Project Aura - Guardrail Configuration Contracts

Data contracts for ADR-069 Guardrail Configuration UI.

Defines the configuration model for user-adjustable guardrail settings
with platform-enforced bounds and compliance profile support.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# =============================================================================
# Enums
# =============================================================================


class SecurityProfile(Enum):
    """
    Security profile presets that control overall guardrail behavior.

    Conservative: Maximum safety, minimal auto-approval
    Balanced: Default, reasonable safety with good productivity
    Efficient: Higher auto-approval, fewer interruptions
    Aggressive: Maximum productivity, minimal safety friction
    """

    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    EFFICIENT = "efficient"
    AGGRESSIVE = "aggressive"


class HITLSensitivity(Enum):
    """
    Human-in-the-loop escalation sensitivity levels.

    LOW: Escalate on most operations (high human oversight)
    MEDIUM: Escalate on DANGEROUS and CRITICAL operations
    HIGH: Escalate only on CRITICAL operations
    CRITICAL_ONLY: Only escalate on explicitly marked critical operations
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL_ONLY = "critical_only"


class TrustLevel(Enum):
    """
    Minimum context trust level required for auto-approval.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ALL = "all"

    def __ge__(self, other: "TrustLevel") -> bool:
        order = {
            TrustLevel.ALL: 0,
            TrustLevel.LOW: 1,
            TrustLevel.MEDIUM: 2,
            TrustLevel.HIGH: 3,
        }
        return order[self] >= order[other]

    def __gt__(self, other: "TrustLevel") -> bool:
        order = {
            TrustLevel.ALL: 0,
            TrustLevel.LOW: 1,
            TrustLevel.MEDIUM: 2,
            TrustLevel.HIGH: 3,
        }
        return order[self] > order[other]

    def __le__(self, other: "TrustLevel") -> bool:
        order = {
            TrustLevel.ALL: 0,
            TrustLevel.LOW: 1,
            TrustLevel.MEDIUM: 2,
            TrustLevel.HIGH: 3,
        }
        return order[self] <= order[other]

    def __lt__(self, other: "TrustLevel") -> bool:
        order = {
            TrustLevel.ALL: 0,
            TrustLevel.LOW: 1,
            TrustLevel.MEDIUM: 2,
            TrustLevel.HIGH: 3,
        }
        return order[self] < order[other]


class Verbosity(Enum):
    """
    Explanation verbosity levels for ADR-068 Universal Explainability.
    """

    MINIMAL = "minimal"
    STANDARD = "standard"
    DETAILED = "detailed"
    DEBUG = "debug"


class ReviewerType(Enum):
    """
    Quarantine review delegation options.
    """

    SELF = "self"
    TEAM_LEAD = "team_lead"
    SECURITY_TEAM = "security_team"


class ComplianceProfile(Enum):
    """
    Compliance profiles that override user preferences when activated.
    """

    NONE = "none"
    SOC2 = "soc2"
    CMMC_L2 = "cmmc_l2"
    CMMC_L3 = "cmmc_l3"
    FEDRAMP_MODERATE = "fedramp_moderate"
    FEDRAMP_HIGH = "fedramp_high"


class ToolTier(Enum):
    """
    Tool classification tiers for capability governance.
    """

    SAFE = "safe"
    MONITORING = "monitoring"
    DANGEROUS = "dangerous"
    CRITICAL = "critical"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ToolGrant:
    """
    A temporary or permanent grant of tool access to a project.
    """

    tool_name: str
    granted_tier: ToolTier
    granted_by: str
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    justification: str = ""

    def is_expired(self) -> bool:
        """Check if grant has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "granted_tier": self.granted_tier.value,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "justification": self.justification,
        }


@dataclass
class ThreatPattern:
    """
    Custom threat pattern for ADR-065 Semantic Guardrails Engine.
    """

    pattern_id: str
    pattern_name: str
    pattern_regex: str
    description: str
    severity: str = "medium"  # low, medium, high, critical
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "pattern_regex": self.pattern_regex,
            "description": self.description,
            "severity": self.severity,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "enabled": self.enabled,
        }


@dataclass
class GuardrailConfiguration:
    """
    User-configurable guardrail settings.

    Tier 2 settings are user-configurable within bounds.
    Tier 3 settings are admin-only.
    """

    # Identity
    tenant_id: str = ""
    user_id: str = ""

    # Tier 2: User-configurable
    security_profile: SecurityProfile = SecurityProfile.BALANCED
    hitl_sensitivity: HITLSensitivity = HITLSensitivity.MEDIUM
    min_context_trust: TrustLevel = TrustLevel.MEDIUM
    explanation_verbosity: Verbosity = Verbosity.STANDARD
    quarantine_reviewer: ReviewerType = ReviewerType.TEAM_LEAD

    # Per-project overrides
    project_tool_grants: dict[str, list[ToolGrant]] = field(default_factory=dict)

    # Tier 3: Admin-only
    custom_threat_patterns: list[ThreatPattern] = field(default_factory=list)
    trust_weight_adjustments: dict[str, float] = field(default_factory=dict)
    tool_tier_overrides: dict[str, ToolTier] = field(default_factory=dict)
    audit_retention_days: int = 365
    compliance_profile: ComplianceProfile = ComplianceProfile.NONE

    # Metadata
    last_modified_by: str = ""
    last_modified_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    change_justification: str = ""
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "security_profile": self.security_profile.value,
            "hitl_sensitivity": self.hitl_sensitivity.value,
            "min_context_trust": self.min_context_trust.value,
            "explanation_verbosity": self.explanation_verbosity.value,
            "quarantine_reviewer": self.quarantine_reviewer.value,
            "project_tool_grants": {
                k: [g.to_dict() for g in v] for k, v in self.project_tool_grants.items()
            },
            "custom_threat_patterns": [
                p.to_dict() for p in self.custom_threat_patterns
            ],
            "trust_weight_adjustments": self.trust_weight_adjustments,
            "tool_tier_overrides": {
                k: v.value for k, v in self.tool_tier_overrides.items()
            },
            "audit_retention_days": self.audit_retention_days,
            "compliance_profile": self.compliance_profile.value,
            "last_modified_by": self.last_modified_by,
            "last_modified_at": self.last_modified_at.isoformat(),
            "change_justification": self.change_justification,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuardrailConfiguration":
        """Create from dictionary."""
        # Convert project_tool_grants
        project_grants = {}
        for project_id, grants in data.get("project_tool_grants", {}).items():
            project_grants[project_id] = [
                ToolGrant(
                    tool_name=g["tool_name"],
                    granted_tier=ToolTier(g["granted_tier"]),
                    granted_by=g["granted_by"],
                    granted_at=datetime.fromisoformat(g["granted_at"]),
                    expires_at=(
                        datetime.fromisoformat(g["expires_at"])
                        if g.get("expires_at")
                        else None
                    ),
                    justification=g.get("justification", ""),
                )
                for g in grants
            ]

        # Convert custom_threat_patterns
        patterns = [
            ThreatPattern(
                pattern_id=p["pattern_id"],
                pattern_name=p["pattern_name"],
                pattern_regex=p["pattern_regex"],
                description=p["description"],
                severity=p.get("severity", "medium"),
                created_by=p.get("created_by", ""),
                created_at=datetime.fromisoformat(p["created_at"]),
                enabled=p.get("enabled", True),
            )
            for p in data.get("custom_threat_patterns", [])
        ]

        # Convert tool_tier_overrides
        tier_overrides = {
            k: ToolTier(v) for k, v in data.get("tool_tier_overrides", {}).items()
        }

        return cls(
            tenant_id=data.get("tenant_id", ""),
            user_id=data.get("user_id", ""),
            security_profile=SecurityProfile(data.get("security_profile", "balanced")),
            hitl_sensitivity=HITLSensitivity(data.get("hitl_sensitivity", "medium")),
            min_context_trust=TrustLevel(data.get("min_context_trust", "medium")),
            explanation_verbosity=Verbosity(
                data.get("explanation_verbosity", "standard")
            ),
            quarantine_reviewer=ReviewerType(
                data.get("quarantine_reviewer", "team_lead")
            ),
            project_tool_grants=project_grants,
            custom_threat_patterns=patterns,
            trust_weight_adjustments=data.get("trust_weight_adjustments", {}),
            tool_tier_overrides=tier_overrides,
            audit_retention_days=data.get("audit_retention_days", 365),
            compliance_profile=ComplianceProfile(
                data.get("compliance_profile", "none")
            ),
            last_modified_by=data.get("last_modified_by", ""),
            last_modified_at=(
                datetime.fromisoformat(data["last_modified_at"])
                if data.get("last_modified_at")
                else datetime.now(timezone.utc)
            ),
            change_justification=data.get("change_justification", ""),
            version=data.get("version", 1),
        )


@dataclass
class ConfigurationChangeRecord:
    """
    Audit record for configuration changes.
    """

    record_id: str
    timestamp: datetime
    user_id: str
    tenant_id: str
    setting_path: str
    previous_value: Any
    new_value: Any
    justification: str = ""
    approved_by: Optional[str] = None
    compliance_profile: ComplianceProfile = ComplianceProfile.NONE
    change_type: str = "update"  # create, update, delete, reset

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "setting_path": self.setting_path,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
            "justification": self.justification,
            "approved_by": self.approved_by,
            "compliance_profile": self.compliance_profile.value,
            "change_type": self.change_type,
        }


@dataclass
class ValidationError:
    """
    Validation error for configuration changes.
    """

    field: str
    message: str
    error_code: str
    severity: str = "error"  # error, warning

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field": self.field,
            "message": self.message,
            "error_code": self.error_code,
            "severity": self.severity,
        }


@dataclass
class ValidationResult:
    """
    Result of configuration validation.
    """

    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    effective_config: Optional[GuardrailConfiguration] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "effective_config": (
                self.effective_config.to_dict() if self.effective_config else None
            ),
        }


# =============================================================================
# Security Profile Specifications
# =============================================================================


SECURITY_PROFILE_SPECS: dict[SecurityProfile, dict[str, Any]] = {
    SecurityProfile.CONSERVATIVE: {
        "hitl_threshold": HITLSensitivity.LOW,
        "auto_approve_tiers": [ToolTier.SAFE],
        "context_trust": TrustLevel.HIGH,
        "explanation": Verbosity.DETAILED,
    },
    SecurityProfile.BALANCED: {
        "hitl_threshold": HITLSensitivity.MEDIUM,
        "auto_approve_tiers": [ToolTier.SAFE, ToolTier.MONITORING],
        "context_trust": TrustLevel.MEDIUM,
        "explanation": Verbosity.STANDARD,
    },
    SecurityProfile.EFFICIENT: {
        "hitl_threshold": HITLSensitivity.HIGH,
        "auto_approve_tiers": [ToolTier.SAFE, ToolTier.MONITORING],
        "context_trust": TrustLevel.MEDIUM,
        "explanation": Verbosity.STANDARD,
    },
    SecurityProfile.AGGRESSIVE: {
        "hitl_threshold": HITLSensitivity.CRITICAL_ONLY,
        "auto_approve_tiers": [ToolTier.SAFE, ToolTier.MONITORING, ToolTier.DANGEROUS],
        "context_trust": TrustLevel.LOW,
        "explanation": Verbosity.MINIMAL,
    },
}


# =============================================================================
# Platform Minimum Thresholds
# =============================================================================


PLATFORM_MINIMUMS: dict[str, Any] = {
    "min_audit_retention_days": 90,
    "max_audit_retention_days": 2555,  # 7 years
    "trust_weight_min_adjustment": -0.15,  # -15%
    "trust_weight_max_adjustment": 0.15,  # +15%
    "hitl_required_for_critical": True,  # Always require HITL for CRITICAL
    "threat_detection_always_active": True,
    "trust_verification_always_active": True,
    "explanation_generation_always_active": True,
}
