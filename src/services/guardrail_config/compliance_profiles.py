"""
Project Aura - Compliance Profile Definitions

Defines compliance profiles that override user preferences when activated.
Implements ADR-069 Guardrail Configuration UI.
"""

from dataclasses import dataclass, field
from typing import Any

from .contracts import ComplianceProfile, ToolTier, TrustLevel, Verbosity


@dataclass
class ComplianceProfileSpec:
    """
    Specification for a compliance profile.

    Defines which settings are locked and what behaviors are enforced.
    """

    profile: ComplianceProfile
    name: str
    description: str

    # Locked settings (cannot be changed by user)
    min_context_trust_level: TrustLevel | None = None
    hitl_required_for: list[ToolTier] = field(default_factory=list)
    min_audit_retention_days: int | None = None
    min_explanation_verbosity: Verbosity | None = None
    credential_tool_tier: ToolTier | None = None

    # Enforced behaviors
    enforced_behaviors: list[str] = field(default_factory=list)

    # Settings that cannot be relaxed below these values
    locked_settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "profile": self.profile.value,
            "name": self.name,
            "description": self.description,
            "min_context_trust_level": (
                self.min_context_trust_level.value
                if self.min_context_trust_level
                else None
            ),
            "hitl_required_for": [t.value for t in self.hitl_required_for],
            "min_audit_retention_days": self.min_audit_retention_days,
            "min_explanation_verbosity": (
                self.min_explanation_verbosity.value
                if self.min_explanation_verbosity
                else None
            ),
            "credential_tool_tier": (
                self.credential_tool_tier.value if self.credential_tool_tier else None
            ),
            "enforced_behaviors": self.enforced_behaviors,
            "locked_settings": self.locked_settings,
        }


# =============================================================================
# Compliance Profile Definitions
# =============================================================================


SOC2_PROFILE = ComplianceProfileSpec(
    profile=ComplianceProfile.SOC2,
    name="SOC 2",
    description="Service Organization Control 2 - Trust Services Criteria",
    min_audit_retention_days=365,
    min_explanation_verbosity=Verbosity.STANDARD,
    enforced_behaviors=[
        "All configuration changes logged with business justification",
        "Quarterly access review required",
    ],
    locked_settings={
        "audit_logging": True,
        "access_review_frequency": "quarterly",
    },
)


CMMC_L2_PROFILE = ComplianceProfileSpec(
    profile=ComplianceProfile.CMMC_L2,
    name="CMMC Level 2",
    description="Cybersecurity Maturity Model Certification Level 2",
    min_context_trust_level=TrustLevel.MEDIUM,
    hitl_required_for=[ToolTier.DANGEROUS, ToolTier.CRITICAL],
    min_audit_retention_days=365,
    min_explanation_verbosity=Verbosity.STANDARD,
    credential_tool_tier=ToolTier.CRITICAL,
    enforced_behaviors=[
        "All HITL escalations require MFA authentication",
        "Configuration changes require supervisor approval",
        "Quarantine release requires security team review",
    ],
    locked_settings={
        "mfa_for_hitl": True,
        "supervisor_approval_for_config": True,
        "security_team_quarantine_review": True,
    },
)


CMMC_L3_PROFILE = ComplianceProfileSpec(
    profile=ComplianceProfile.CMMC_L3,
    name="CMMC Level 3",
    description="Cybersecurity Maturity Model Certification Level 3",
    min_context_trust_level=TrustLevel.HIGH,
    hitl_required_for=[ToolTier.MONITORING, ToolTier.DANGEROUS, ToolTier.CRITICAL],
    min_audit_retention_days=365,
    min_explanation_verbosity=Verbosity.DETAILED,
    credential_tool_tier=ToolTier.CRITICAL,
    enforced_behaviors=[
        "All HITL escalations require CAC/PIV authentication",
        "Configuration changes require supervisor approval",
        "Quarantine release requires security team review",
        "All tool tier overrides require security officer approval",
    ],
    locked_settings={
        "cac_piv_for_hitl": True,
        "supervisor_approval_for_config": True,
        "security_team_quarantine_review": True,
        "security_officer_tier_approval": True,
    },
)


FEDRAMP_MODERATE_PROFILE = ComplianceProfileSpec(
    profile=ComplianceProfile.FEDRAMP_MODERATE,
    name="FedRAMP Moderate",
    description="Federal Risk and Authorization Management Program - Moderate Impact",
    min_context_trust_level=TrustLevel.MEDIUM,
    hitl_required_for=[ToolTier.DANGEROUS, ToolTier.CRITICAL],
    min_audit_retention_days=1095,  # 3 years
    min_explanation_verbosity=Verbosity.DETAILED,
    credential_tool_tier=ToolTier.CRITICAL,
    enforced_behaviors=[
        "All configuration changes logged with justification",
        "Decisions exportable for ATO evidence",
        "Quarterly review of guardrail settings",
    ],
    locked_settings={
        "export_for_ato": True,
        "quarterly_review": True,
    },
)


FEDRAMP_HIGH_PROFILE = ComplianceProfileSpec(
    profile=ComplianceProfile.FEDRAMP_HIGH,
    name="FedRAMP High",
    description="Federal Risk and Authorization Management Program - High Impact",
    min_context_trust_level=TrustLevel.HIGH,
    hitl_required_for=[ToolTier.MONITORING, ToolTier.DANGEROUS, ToolTier.CRITICAL],
    min_audit_retention_days=2555,  # 7 years
    min_explanation_verbosity=Verbosity.DETAILED,
    credential_tool_tier=ToolTier.CRITICAL,
    enforced_behaviors=[
        "Admin settings require 2-person approval",
        "All decisions exportable for POAM evidence",
        "No reduction in security posture without ISSO approval",
        "Monthly security configuration review",
    ],
    locked_settings={
        "two_person_approval": True,
        "export_for_poam": True,
        "isso_approval_for_reduction": True,
        "monthly_review": True,
    },
)


# Registry of all compliance profiles
COMPLIANCE_PROFILES: dict[ComplianceProfile, ComplianceProfileSpec] = {
    ComplianceProfile.SOC2: SOC2_PROFILE,
    ComplianceProfile.CMMC_L2: CMMC_L2_PROFILE,
    ComplianceProfile.CMMC_L3: CMMC_L3_PROFILE,
    ComplianceProfile.FEDRAMP_MODERATE: FEDRAMP_MODERATE_PROFILE,
    ComplianceProfile.FEDRAMP_HIGH: FEDRAMP_HIGH_PROFILE,
}


def get_compliance_profile(profile: ComplianceProfile) -> ComplianceProfileSpec | None:
    """Get the specification for a compliance profile."""
    return COMPLIANCE_PROFILES.get(profile)


def list_compliance_profiles() -> list[ComplianceProfileSpec]:
    """List all available compliance profiles."""
    return list(COMPLIANCE_PROFILES.values())


def get_hitl_requirements(profile: ComplianceProfile) -> list[ToolTier]:
    """Get the HITL requirements for a compliance profile."""
    spec = get_compliance_profile(profile)
    if spec:
        return spec.hitl_required_for
    return []


def get_minimum_trust_level(profile: ComplianceProfile) -> TrustLevel | None:
    """Get the minimum trust level for a compliance profile."""
    spec = get_compliance_profile(profile)
    if spec:
        return spec.min_context_trust_level
    return None


def get_minimum_audit_retention(profile: ComplianceProfile) -> int | None:
    """Get the minimum audit retention days for a compliance profile."""
    spec = get_compliance_profile(profile)
    if spec:
        return spec.min_audit_retention_days
    return None


def get_minimum_verbosity(profile: ComplianceProfile) -> Verbosity | None:
    """Get the minimum explanation verbosity for a compliance profile."""
    spec = get_compliance_profile(profile)
    if spec:
        return spec.min_explanation_verbosity
    return None


def is_setting_locked(profile: ComplianceProfile, setting_name: str) -> bool:
    """Check if a setting is locked by a compliance profile."""
    spec = get_compliance_profile(profile)
    if spec and setting_name in spec.locked_settings:
        return True
    return False
