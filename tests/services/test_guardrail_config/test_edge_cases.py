"""
Extended edge case tests for guardrail configuration services (ADR-069).

Tests additional edge cases and error paths not covered in main test files.
"""

import platform
from datetime import datetime, timezone

import pytest

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.guardrail_config import (
    PLATFORM_MINIMUMS,
    SECURITY_PROFILE_SPECS,
    ComplianceProfile,
    ConfigurationChangeRecord,
    GuardrailConfiguration,
    HITLSensitivity,
    ReviewerType,
    SecurityProfile,
    ThreatPattern,
    ToolGrant,
    ToolTier,
    TrustLevel,
    ValidationError,
    ValidationResult,
    Verbosity,
    get_config_service,
    get_hitl_requirements,
    get_minimum_audit_retention,
    get_minimum_trust_level,
    get_minimum_verbosity,
    get_validation_service,
    is_setting_locked,
    list_compliance_profiles,
    reset_config_service,
    reset_validation_service,
)

# =============================================================================
# Configuration Edge Cases
# =============================================================================


class TestConfigurationEdgeCases:
    """Test edge cases for GuardrailConfiguration."""

    def test_configuration_with_empty_strings(self):
        """Test configuration handles empty strings."""
        config = GuardrailConfiguration(
            tenant_id="",
            user_id="",
        )
        assert config.tenant_id == ""
        assert config.user_id == ""

    def test_configuration_with_special_characters(self):
        """Test configuration with special characters in IDs."""
        config = GuardrailConfiguration(
            tenant_id="tenant-123_test@org",
            user_id="user+special@domain.com",
        )
        data = config.to_dict()
        restored = GuardrailConfiguration.from_dict(data)
        assert restored.tenant_id == config.tenant_id
        assert restored.user_id == config.user_id

    def test_configuration_with_all_enum_profiles(self):
        """Test configuration with each security profile."""
        for profile in SecurityProfile:
            config = GuardrailConfiguration(
                tenant_id="test",
                user_id="test",
                security_profile=profile,
            )
            assert config.security_profile == profile

    def test_configuration_with_all_hitl_sensitivities(self):
        """Test configuration with each HITL sensitivity."""
        for sensitivity in HITLSensitivity:
            config = GuardrailConfiguration(
                tenant_id="test",
                user_id="test",
                hitl_sensitivity=sensitivity,
            )
            assert config.hitl_sensitivity == sensitivity

    def test_configuration_with_all_trust_levels(self):
        """Test configuration with each trust level."""
        for level in TrustLevel:
            config = GuardrailConfiguration(
                tenant_id="test",
                user_id="test",
                min_context_trust=level,
            )
            assert config.min_context_trust == level

    def test_configuration_with_all_verbosity_levels(self):
        """Test configuration with each verbosity level."""
        for verbosity in Verbosity:
            config = GuardrailConfiguration(
                tenant_id="test",
                user_id="test",
                explanation_verbosity=verbosity,
            )
            assert config.explanation_verbosity == verbosity

    def test_configuration_with_all_reviewer_types(self):
        """Test configuration with each reviewer type."""
        for reviewer in ReviewerType:
            config = GuardrailConfiguration(
                tenant_id="test",
                user_id="test",
                quarantine_reviewer=reviewer,
            )
            assert config.quarantine_reviewer == reviewer

    def test_configuration_with_all_compliance_profiles(self):
        """Test configuration with each compliance profile."""
        for profile in ComplianceProfile:
            config = GuardrailConfiguration(
                tenant_id="test",
                user_id="test",
                compliance_profile=profile,
            )
            assert config.compliance_profile == profile

    def test_configuration_with_max_audit_retention(self):
        """Test configuration with maximum audit retention."""
        config = GuardrailConfiguration(
            tenant_id="test",
            user_id="test",
            audit_retention_days=2555,
        )
        assert config.audit_retention_days == 2555

    def test_configuration_with_min_audit_retention(self):
        """Test configuration with minimum audit retention."""
        config = GuardrailConfiguration(
            tenant_id="test",
            user_id="test",
            audit_retention_days=90,
        )
        assert config.audit_retention_days == 90


# =============================================================================
# Tool Grant Edge Cases
# =============================================================================


class TestToolGrantEdgeCases:
    """Test edge cases for ToolGrant."""

    def test_tool_grant_with_all_tiers(self):
        """Test tool grant with each tier."""
        for tier in ToolTier:
            grant = ToolGrant(
                tool_name="test_tool",
                granted_tier=tier,
                granted_by="admin",
            )
            assert grant.granted_tier == tier

    def test_tool_grant_to_dict_with_expiry(self):
        """Test tool grant serialization with expiry."""
        from datetime import timedelta

        grant = ToolGrant(
            tool_name="test",
            granted_tier=ToolTier.CRITICAL,
            granted_by="admin",
            justification="Test justification",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        data = grant.to_dict()
        assert "expires_at" in data
        assert data["expires_at"] is not None

    def test_tool_grant_just_expired(self):
        """Test tool grant that just expired."""
        from datetime import timedelta

        grant = ToolGrant(
            tool_name="test",
            granted_tier=ToolTier.SAFE,
            granted_by="admin",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        assert grant.is_expired()


# =============================================================================
# Threat Pattern Edge Cases
# =============================================================================


class TestThreatPatternEdgeCases:
    """Test edge cases for ThreatPattern."""

    def test_threat_pattern_all_severities(self):
        """Test threat pattern with different severities."""
        for severity in ["low", "medium", "high", "critical"]:
            pattern = ThreatPattern(
                pattern_id="test-pattern",
                pattern_name="Test",
                pattern_regex="test",
                description="Test",
                severity=severity,
            )
            assert pattern.severity == severity

    def test_threat_pattern_disabled(self):
        """Test disabled threat pattern."""
        pattern = ThreatPattern(
            pattern_id="test",
            pattern_name="Test",
            pattern_regex="test",
            description="Test",
            enabled=False,
        )
        assert pattern.enabled is False

    def test_threat_pattern_with_creator(self):
        """Test threat pattern with creator info."""
        pattern = ThreatPattern(
            pattern_id="test",
            pattern_name="SQL Injection Pattern",
            pattern_regex="(?i)(union|select|insert|delete|drop|update)",
            description="Detects common SQL injection patterns",
            created_by="security-team",
        )
        assert pattern.created_by == "security-team"

    def test_threat_pattern_to_dict(self):
        """Test threat pattern serialization."""
        pattern = ThreatPattern(
            pattern_id="test-001",
            pattern_name="Test Pattern",
            pattern_regex="test.*",
            description="Test description",
            severity="high",
        )
        data = pattern.to_dict()
        assert data["pattern_id"] == "test-001"
        assert data["severity"] == "high"
        assert "created_at" in data


# =============================================================================
# Validation Result Edge Cases
# =============================================================================


class TestValidationResultEdgeCases:
    """Test edge cases for ValidationResult."""

    def test_validation_result_with_multiple_errors(self):
        """Test result with multiple errors."""
        errors = [
            ValidationError(field="field1", message="Error 1", error_code="E1"),
            ValidationError(field="field2", message="Error 2", error_code="E2"),
            ValidationError(field="field3", message="Error 3", error_code="E3"),
        ]
        result = ValidationResult(valid=False, errors=errors)
        assert len(result.errors) == 3

    def test_validation_result_with_multiple_warnings(self):
        """Test result with multiple warnings."""
        warnings = [
            ValidationError(
                field="field1", message="Warning 1", error_code="W1", severity="warning"
            ),
            ValidationError(
                field="field2", message="Warning 2", error_code="W2", severity="warning"
            ),
        ]
        result = ValidationResult(valid=True, warnings=warnings)
        assert len(result.warnings) == 2
        assert result.valid is True

    def test_validation_result_mixed_errors_warnings(self):
        """Test result with both errors and warnings."""
        errors = [ValidationError(field="f1", message="Error", error_code="E1")]
        warnings = [
            ValidationError(
                field="f2", message="Warning", error_code="W1", severity="warning"
            )
        ]
        result = ValidationResult(valid=False, errors=errors, warnings=warnings)
        assert len(result.errors) == 1
        assert len(result.warnings) == 1


# =============================================================================
# Configuration Change Record Edge Cases
# =============================================================================


class TestChangeRecordEdgeCases:
    """Test edge cases for ConfigurationChangeRecord."""

    def test_change_record_create_type(self):
        """Test change record with create type."""
        record = ConfigurationChangeRecord(
            record_id="test-001",
            timestamp=datetime.now(timezone.utc),
            user_id="user",
            tenant_id="tenant",
            setting_path="security_profile",
            previous_value=None,
            new_value="balanced",
            change_type="create",
        )
        assert record.change_type == "create"

    def test_change_record_delete_type(self):
        """Test change record with delete type."""
        record = ConfigurationChangeRecord(
            record_id="test-002",
            timestamp=datetime.now(timezone.utc),
            user_id="user",
            tenant_id="tenant",
            setting_path="security_profile",
            previous_value="balanced",
            new_value=None,
            change_type="delete",
        )
        assert record.change_type == "delete"

    def test_change_record_reset_type(self):
        """Test change record with reset type."""
        record = ConfigurationChangeRecord(
            record_id="test-003",
            timestamp=datetime.now(timezone.utc),
            user_id="user",
            tenant_id="tenant",
            setting_path="*",
            previous_value="custom",
            new_value="default",
            change_type="reset",
        )
        assert record.change_type == "reset"


# =============================================================================
# Compliance Profile Edge Cases
# =============================================================================


class TestComplianceProfileEdgeCases:
    """Test edge cases for compliance profile functions."""

    def test_list_compliance_profiles_returns_all(self):
        """Test listing all compliance profiles."""
        profiles = list_compliance_profiles()
        assert len(profiles) >= 5  # SOC2, CMMC L2, CMMC L3, FedRAMP Moderate, High

    def test_get_hitl_requirements_all_profiles(self):
        """Test getting HITL requirements for all profiles."""
        for profile in ComplianceProfile:
            requirements = get_hitl_requirements(profile)
            assert isinstance(requirements, list)

    def test_get_minimum_trust_level_all_profiles(self):
        """Test getting minimum trust level for all profiles."""
        for profile in ComplianceProfile:
            level = get_minimum_trust_level(profile)
            assert level is None or isinstance(level, TrustLevel)

    def test_get_minimum_audit_retention_all_profiles(self):
        """Test getting minimum audit retention for all profiles."""
        for profile in ComplianceProfile:
            retention = get_minimum_audit_retention(profile)
            assert retention is None or isinstance(retention, int)

    def test_get_minimum_verbosity_all_profiles(self):
        """Test getting minimum verbosity for all profiles."""
        for profile in ComplianceProfile:
            verbosity = get_minimum_verbosity(profile)
            assert verbosity is None or isinstance(verbosity, Verbosity)

    def test_is_setting_locked_various_settings(self):
        """Test checking if various settings are locked."""
        settings_to_check = [
            "audit_logging",
            "two_person_approval",
            "encryption",
            "nonexistent_setting",
        ]
        for setting in settings_to_check:
            for profile in ComplianceProfile:
                result = is_setting_locked(profile, setting)
                assert isinstance(result, bool)


# =============================================================================
# Security Profile Specs Edge Cases
# =============================================================================


class TestSecurityProfileSpecsEdgeCases:
    """Test edge cases for security profile specifications."""

    def test_all_profiles_have_specs(self):
        """Test all security profiles have specifications."""
        for profile in SecurityProfile:
            assert profile in SECURITY_PROFILE_SPECS

    def test_all_specs_have_required_keys(self):
        """Test all specs have required keys."""
        required_keys = ["hitl_threshold", "context_trust", "explanation"]
        for profile, spec in SECURITY_PROFILE_SPECS.items():
            for key in required_keys:
                assert key in spec, f"Profile {profile} missing key {key}"


# =============================================================================
# Platform Minimums Edge Cases
# =============================================================================


class TestPlatformMinimumsEdgeCases:
    """Test edge cases for platform minimum thresholds."""

    def test_all_minimums_present(self):
        """Test all minimum thresholds are present."""
        required_keys = [
            "min_audit_retention_days",
            "max_audit_retention_days",
            "trust_weight_min_adjustment",
            "trust_weight_max_adjustment",
            "hitl_required_for_critical",
            "threat_detection_always_active",
            "trust_verification_always_active",
            "explanation_generation_always_active",
        ]
        for key in required_keys:
            assert key in PLATFORM_MINIMUMS

    def test_minimums_are_correct_types(self):
        """Test minimum values are correct types."""
        assert isinstance(PLATFORM_MINIMUMS["min_audit_retention_days"], int)
        assert isinstance(PLATFORM_MINIMUMS["max_audit_retention_days"], int)
        assert isinstance(PLATFORM_MINIMUMS["trust_weight_min_adjustment"], float)
        assert isinstance(PLATFORM_MINIMUMS["trust_weight_max_adjustment"], float)
        assert isinstance(PLATFORM_MINIMUMS["hitl_required_for_critical"], bool)


# =============================================================================
# Trust Level Comparison Edge Cases
# =============================================================================


class TestTrustLevelComparisonEdgeCases:
    """Test edge cases for TrustLevel comparisons."""

    def test_trust_level_equals(self):
        """Test trust level equality."""
        assert TrustLevel.HIGH == TrustLevel.HIGH
        assert TrustLevel.MEDIUM == TrustLevel.MEDIUM
        assert TrustLevel.LOW == TrustLevel.LOW
        assert TrustLevel.ALL == TrustLevel.ALL

    def test_trust_level_not_equals(self):
        """Test trust level inequality."""
        assert TrustLevel.HIGH != TrustLevel.LOW
        assert TrustLevel.MEDIUM != TrustLevel.ALL

    def test_trust_level_full_ordering(self):
        """Test full ordering of trust levels."""
        levels = [TrustLevel.ALL, TrustLevel.LOW, TrustLevel.MEDIUM, TrustLevel.HIGH]
        # HIGH > MEDIUM > LOW > ALL
        assert levels == sorted(levels)

    def test_trust_level_less_than_or_equal(self):
        """Test less than or equal for trust levels."""
        assert TrustLevel.ALL <= TrustLevel.ALL
        assert TrustLevel.ALL <= TrustLevel.LOW
        assert TrustLevel.LOW <= TrustLevel.MEDIUM
        assert TrustLevel.MEDIUM <= TrustLevel.HIGH


# =============================================================================
# Service Singleton Edge Cases
# =============================================================================


class TestServiceSingletonEdgeCases:
    """Test edge cases for service singletons."""

    @pytest.fixture(autouse=True)
    def reset_services(self):
        """Reset services before and after each test."""
        reset_config_service()
        reset_validation_service()
        yield
        reset_config_service()
        reset_validation_service()

    def test_get_config_service_creates_instance(self):
        """Test get_config_service creates a new instance."""
        service = get_config_service()
        assert service is not None

    def test_get_validation_service_creates_instance(self):
        """Test get_validation_service creates a new instance."""
        service = get_validation_service()
        assert service is not None

    def test_services_are_singletons(self):
        """Test services return the same instance."""
        service1 = get_config_service()
        service2 = get_config_service()
        assert service1 is service2

        vs1 = get_validation_service()
        vs2 = get_validation_service()
        assert vs1 is vs2

    def test_reset_creates_new_instance(self):
        """Test reset creates new instances."""
        service1 = get_config_service()
        reset_config_service()
        service2 = get_config_service()
        assert service1 is not service2


# =============================================================================
# Configuration Serialization Edge Cases
# =============================================================================


class TestConfigurationSerializationEdgeCases:
    """Test edge cases for configuration serialization."""

    def test_roundtrip_with_complex_overrides(self):
        """Test roundtrip with complex tool tier overrides."""
        config = GuardrailConfiguration(
            tenant_id="test",
            user_id="test",
            tool_tier_overrides={
                "read_file": ToolTier.SAFE,
                "write_file": ToolTier.MONITORING,
                "execute_command": ToolTier.DANGEROUS,
                "deploy_production": ToolTier.CRITICAL,
            },
        )
        data = config.to_dict()
        restored = GuardrailConfiguration.from_dict(data)
        assert restored.tool_tier_overrides == config.tool_tier_overrides

    def test_roundtrip_with_trust_adjustments(self):
        """Test roundtrip with trust weight adjustments."""
        config = GuardrailConfiguration(
            tenant_id="test",
            user_id="test",
            trust_weight_adjustments={
                "internal": 0.15,
                "external": -0.10,
                "partner": 0.05,
            },
        )
        data = config.to_dict()
        restored = GuardrailConfiguration.from_dict(data)
        assert restored.trust_weight_adjustments == config.trust_weight_adjustments

    def test_roundtrip_with_threat_patterns(self):
        """Test roundtrip with custom threat patterns."""
        pattern = ThreatPattern(
            pattern_id="test-001",
            pattern_name="Test Pattern",
            pattern_regex=r"SELECT.*FROM",
            description="Test description",
            severity="high",
        )
        config = GuardrailConfiguration(
            tenant_id="test",
            user_id="test",
            custom_threat_patterns=[pattern],
        )
        data = config.to_dict()
        restored = GuardrailConfiguration.from_dict(data)
        assert len(restored.custom_threat_patterns) == 1
        assert restored.custom_threat_patterns[0].pattern_id == "test-001"

    def test_roundtrip_with_tool_grants(self):
        """Test roundtrip with project tool grants."""
        grant = ToolGrant(
            tool_name="deploy",
            granted_tier=ToolTier.CRITICAL,
            granted_by="admin",
            justification="Production access",
        )
        config = GuardrailConfiguration(
            tenant_id="test",
            user_id="test",
            project_tool_grants={"project-1": [grant]},
        )
        data = config.to_dict()
        restored = GuardrailConfiguration.from_dict(data)
        assert "project-1" in restored.project_tool_grants
        assert len(restored.project_tool_grants["project-1"]) == 1
