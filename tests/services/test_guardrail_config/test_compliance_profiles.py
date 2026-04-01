"""
Tests for compliance profile definitions (ADR-069).
"""

from src.services.guardrail_config import (
    COMPLIANCE_PROFILES,
    ComplianceProfile,
    ComplianceProfileSpec,
    ToolTier,
    TrustLevel,
    Verbosity,
    get_compliance_profile,
    get_hitl_requirements,
    get_minimum_audit_retention,
    get_minimum_trust_level,
    get_minimum_verbosity,
    is_setting_locked,
    list_compliance_profiles,
)


class TestComplianceProfileRegistry:
    """Tests for compliance profile registry."""

    def test_all_profiles_registered(self):
        """Test all compliance profiles are registered."""
        # NONE is intentionally not in the registry
        expected_profiles = {
            ComplianceProfile.SOC2,
            ComplianceProfile.CMMC_L2,
            ComplianceProfile.CMMC_L3,
            ComplianceProfile.FEDRAMP_MODERATE,
            ComplianceProfile.FEDRAMP_HIGH,
        }
        assert set(COMPLIANCE_PROFILES.keys()) == expected_profiles

    def test_list_compliance_profiles(self):
        """Test listing all compliance profiles."""
        profiles = list_compliance_profiles()
        assert len(profiles) == 5
        assert all(isinstance(p, ComplianceProfileSpec) for p in profiles)

    def test_get_compliance_profile_exists(self):
        """Test getting existing compliance profile."""
        profile = get_compliance_profile(ComplianceProfile.SOC2)
        assert profile is not None
        assert profile.profile == ComplianceProfile.SOC2

    def test_get_compliance_profile_not_found(self):
        """Test getting non-existent compliance profile."""
        profile = get_compliance_profile(ComplianceProfile.NONE)
        assert profile is None


class TestSOC2Profile:
    """Tests for SOC 2 compliance profile."""

    def test_soc2_basic_properties(self):
        """Test SOC2 profile basic properties."""
        profile = get_compliance_profile(ComplianceProfile.SOC2)
        assert profile.name == "SOC 2"
        assert "Trust Services" in profile.description

    def test_soc2_audit_retention(self):
        """Test SOC2 audit retention requirement."""
        profile = get_compliance_profile(ComplianceProfile.SOC2)
        assert profile.min_audit_retention_days == 365

    def test_soc2_verbosity(self):
        """Test SOC2 verbosity requirement."""
        profile = get_compliance_profile(ComplianceProfile.SOC2)
        assert profile.min_explanation_verbosity == Verbosity.STANDARD

    def test_soc2_enforced_behaviors(self):
        """Test SOC2 enforced behaviors."""
        profile = get_compliance_profile(ComplianceProfile.SOC2)
        assert len(profile.enforced_behaviors) >= 2
        assert any("logged" in b.lower() for b in profile.enforced_behaviors)

    def test_soc2_locked_settings(self):
        """Test SOC2 locked settings."""
        profile = get_compliance_profile(ComplianceProfile.SOC2)
        assert profile.locked_settings.get("audit_logging") is True

    def test_soc2_to_dict(self):
        """Test SOC2 profile serialization."""
        profile = get_compliance_profile(ComplianceProfile.SOC2)
        data = profile.to_dict()
        assert data["profile"] == "soc2"
        assert data["min_audit_retention_days"] == 365


class TestCMMCL2Profile:
    """Tests for CMMC Level 2 compliance profile."""

    def test_cmmc_l2_basic_properties(self):
        """Test CMMC L2 profile basic properties."""
        profile = get_compliance_profile(ComplianceProfile.CMMC_L2)
        assert profile.name == "CMMC Level 2"
        assert "Cybersecurity" in profile.description

    def test_cmmc_l2_trust_level(self):
        """Test CMMC L2 trust level requirement."""
        profile = get_compliance_profile(ComplianceProfile.CMMC_L2)
        assert profile.min_context_trust_level == TrustLevel.MEDIUM

    def test_cmmc_l2_hitl_requirements(self):
        """Test CMMC L2 HITL requirements."""
        profile = get_compliance_profile(ComplianceProfile.CMMC_L2)
        assert ToolTier.DANGEROUS in profile.hitl_required_for
        assert ToolTier.CRITICAL in profile.hitl_required_for

    def test_cmmc_l2_credential_tier(self):
        """Test CMMC L2 credential tool tier."""
        profile = get_compliance_profile(ComplianceProfile.CMMC_L2)
        assert profile.credential_tool_tier == ToolTier.CRITICAL

    def test_cmmc_l2_enforced_behaviors(self):
        """Test CMMC L2 enforced behaviors."""
        profile = get_compliance_profile(ComplianceProfile.CMMC_L2)
        assert any("MFA" in b for b in profile.enforced_behaviors)
        assert any("supervisor" in b.lower() for b in profile.enforced_behaviors)


class TestCMMCL3Profile:
    """Tests for CMMC Level 3 compliance profile."""

    def test_cmmc_l3_basic_properties(self):
        """Test CMMC L3 profile basic properties."""
        profile = get_compliance_profile(ComplianceProfile.CMMC_L3)
        assert profile.name == "CMMC Level 3"

    def test_cmmc_l3_trust_level(self):
        """Test CMMC L3 trust level requirement."""
        profile = get_compliance_profile(ComplianceProfile.CMMC_L3)
        assert profile.min_context_trust_level == TrustLevel.HIGH

    def test_cmmc_l3_hitl_requirements(self):
        """Test CMMC L3 HITL requirements include MONITORING."""
        profile = get_compliance_profile(ComplianceProfile.CMMC_L3)
        assert ToolTier.MONITORING in profile.hitl_required_for
        assert ToolTier.DANGEROUS in profile.hitl_required_for
        assert ToolTier.CRITICAL in profile.hitl_required_for

    def test_cmmc_l3_verbosity(self):
        """Test CMMC L3 verbosity requirement."""
        profile = get_compliance_profile(ComplianceProfile.CMMC_L3)
        assert profile.min_explanation_verbosity == Verbosity.DETAILED

    def test_cmmc_l3_enforced_behaviors(self):
        """Test CMMC L3 enforced behaviors."""
        profile = get_compliance_profile(ComplianceProfile.CMMC_L3)
        assert any("CAC" in b or "PIV" in b for b in profile.enforced_behaviors)


class TestFedRAMPModerateProfile:
    """Tests for FedRAMP Moderate compliance profile."""

    def test_fedramp_moderate_basic_properties(self):
        """Test FedRAMP Moderate profile basic properties."""
        profile = get_compliance_profile(ComplianceProfile.FEDRAMP_MODERATE)
        assert profile.name == "FedRAMP Moderate"
        assert "Moderate Impact" in profile.description

    def test_fedramp_moderate_audit_retention(self):
        """Test FedRAMP Moderate audit retention (3 years)."""
        profile = get_compliance_profile(ComplianceProfile.FEDRAMP_MODERATE)
        assert profile.min_audit_retention_days == 1095  # 3 years

    def test_fedramp_moderate_trust_level(self):
        """Test FedRAMP Moderate trust level requirement."""
        profile = get_compliance_profile(ComplianceProfile.FEDRAMP_MODERATE)
        assert profile.min_context_trust_level == TrustLevel.MEDIUM

    def test_fedramp_moderate_enforced_behaviors(self):
        """Test FedRAMP Moderate enforced behaviors."""
        profile = get_compliance_profile(ComplianceProfile.FEDRAMP_MODERATE)
        assert any("ATO" in b for b in profile.enforced_behaviors)


class TestFedRAMPHighProfile:
    """Tests for FedRAMP High compliance profile."""

    def test_fedramp_high_basic_properties(self):
        """Test FedRAMP High profile basic properties."""
        profile = get_compliance_profile(ComplianceProfile.FEDRAMP_HIGH)
        assert profile.name == "FedRAMP High"
        assert "High Impact" in profile.description

    def test_fedramp_high_audit_retention(self):
        """Test FedRAMP High audit retention (7 years)."""
        profile = get_compliance_profile(ComplianceProfile.FEDRAMP_HIGH)
        assert profile.min_audit_retention_days == 2555  # 7 years

    def test_fedramp_high_trust_level(self):
        """Test FedRAMP High trust level requirement."""
        profile = get_compliance_profile(ComplianceProfile.FEDRAMP_HIGH)
        assert profile.min_context_trust_level == TrustLevel.HIGH

    def test_fedramp_high_hitl_requirements(self):
        """Test FedRAMP High HITL requirements."""
        profile = get_compliance_profile(ComplianceProfile.FEDRAMP_HIGH)
        assert ToolTier.MONITORING in profile.hitl_required_for
        assert ToolTier.DANGEROUS in profile.hitl_required_for
        assert ToolTier.CRITICAL in profile.hitl_required_for

    def test_fedramp_high_enforced_behaviors(self):
        """Test FedRAMP High enforced behaviors."""
        profile = get_compliance_profile(ComplianceProfile.FEDRAMP_HIGH)
        assert any(
            "2-person" in b or "two-person" in b.lower()
            for b in profile.enforced_behaviors
        )
        assert any("ISSO" in b for b in profile.enforced_behaviors)

    def test_fedramp_high_locked_settings(self):
        """Test FedRAMP High locked settings."""
        profile = get_compliance_profile(ComplianceProfile.FEDRAMP_HIGH)
        assert profile.locked_settings.get("two_person_approval") is True


class TestHelperFunctions:
    """Tests for compliance profile helper functions."""

    def test_get_hitl_requirements_cmmc_l2(self):
        """Test getting HITL requirements for CMMC L2."""
        requirements = get_hitl_requirements(ComplianceProfile.CMMC_L2)
        assert ToolTier.DANGEROUS in requirements
        assert ToolTier.CRITICAL in requirements

    def test_get_hitl_requirements_none_profile(self):
        """Test getting HITL requirements for NONE profile."""
        requirements = get_hitl_requirements(ComplianceProfile.NONE)
        assert requirements == []

    def test_get_minimum_trust_level(self):
        """Test getting minimum trust level."""
        assert get_minimum_trust_level(ComplianceProfile.CMMC_L3) == TrustLevel.HIGH
        assert get_minimum_trust_level(ComplianceProfile.CMMC_L2) == TrustLevel.MEDIUM
        assert get_minimum_trust_level(ComplianceProfile.NONE) is None

    def test_get_minimum_audit_retention(self):
        """Test getting minimum audit retention."""
        assert get_minimum_audit_retention(ComplianceProfile.SOC2) == 365
        assert get_minimum_audit_retention(ComplianceProfile.FEDRAMP_HIGH) == 2555
        assert get_minimum_audit_retention(ComplianceProfile.NONE) is None

    def test_get_minimum_verbosity(self):
        """Test getting minimum verbosity."""
        assert get_minimum_verbosity(ComplianceProfile.SOC2) == Verbosity.STANDARD
        assert get_minimum_verbosity(ComplianceProfile.CMMC_L3) == Verbosity.DETAILED
        assert get_minimum_verbosity(ComplianceProfile.NONE) is None

    def test_is_setting_locked(self):
        """Test checking if setting is locked."""
        assert is_setting_locked(ComplianceProfile.SOC2, "audit_logging") is True
        assert is_setting_locked(ComplianceProfile.SOC2, "not_locked_setting") is False
        assert (
            is_setting_locked(ComplianceProfile.FEDRAMP_HIGH, "two_person_approval")
            is True
        )

    def test_is_setting_locked_none_profile(self):
        """Test checking locked settings for NONE profile."""
        assert is_setting_locked(ComplianceProfile.NONE, "audit_logging") is False


class TestComplianceProfileSpec:
    """Tests for ComplianceProfileSpec dataclass."""

    def test_profile_spec_to_dict(self):
        """Test profile spec serialization."""
        profile = get_compliance_profile(ComplianceProfile.CMMC_L2)
        data = profile.to_dict()
        assert data["profile"] == "cmmc_l2"
        assert data["name"] == "CMMC Level 2"
        assert data["min_context_trust_level"] == "medium"
        assert "dangerous" in data["hitl_required_for"]
        assert "critical" in data["hitl_required_for"]

    def test_profile_spec_serialization_optional_fields(self):
        """Test profile spec serialization with None fields."""
        profile = get_compliance_profile(ComplianceProfile.SOC2)
        data = profile.to_dict()
        # SOC2 doesn't require min_context_trust_level
        assert data["min_context_trust_level"] is None
