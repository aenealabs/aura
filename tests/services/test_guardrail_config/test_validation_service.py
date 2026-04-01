"""
Tests for guardrail configuration validation service (ADR-069).
"""

from src.services.guardrail_config import (
    ComplianceProfile,
    GuardrailConfiguration,
    HITLSensitivity,
    SecurityProfile,
    ThreatPattern,
    ToolTier,
    TrustLevel,
    ValidationContext,
    Verbosity,
    get_validation_service,
)


class TestPlatformMinimumValidation:
    """Tests for platform minimum threshold validation."""

    def test_valid_audit_retention(
        self, validation_service, balanced_config, admin_context
    ):
        """Test valid audit retention passes validation."""
        result = validation_service.validate_configuration(
            balanced_config, admin_context
        )
        assert result.valid is True

    def test_audit_retention_below_minimum(self, validation_service, admin_context):
        """Test audit retention below minimum fails."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            audit_retention_days=30,  # Below 90 day minimum
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is False
        assert any(e.error_code == "PLATFORM_MINIMUM_VIOLATION" for e in result.errors)
        assert any(e.field == "audit_retention_days" for e in result.errors)

    def test_audit_retention_above_maximum(self, validation_service, admin_context):
        """Test audit retention above maximum fails."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            audit_retention_days=3000,  # Above 2555 day maximum
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is False
        assert any(e.error_code == "PLATFORM_MAXIMUM_VIOLATION" for e in result.errors)

    def test_trust_weight_within_bounds(self, validation_service, admin_context):
        """Test trust weight adjustments within bounds pass."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            trust_weight_adjustments={"internal": 0.1, "external": -0.1},
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is True

    def test_trust_weight_above_maximum(self, validation_service, admin_context):
        """Test trust weight above maximum fails."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            trust_weight_adjustments={"internal": 0.5},  # Above 0.15 max
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is False
        assert any(e.error_code == "PLATFORM_BOUNDS_VIOLATION" for e in result.errors)

    def test_trust_weight_below_minimum(self, validation_service, admin_context):
        """Test trust weight below minimum fails."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            trust_weight_adjustments={"external": -0.5},  # Below -0.15 min
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is False
        assert any(e.error_code == "PLATFORM_BOUNDS_VIOLATION" for e in result.errors)


class TestComplianceProfileValidation:
    """Tests for compliance profile lock validation."""

    def test_soc2_audit_retention_enforced(self, validation_service, soc2_context):
        """Test SOC2 enforces minimum audit retention."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            audit_retention_days=180,  # Below SOC2's 365 requirement
            compliance_profile=ComplianceProfile.SOC2,
        )
        result = validation_service.validate_configuration(config, soc2_context)
        assert result.valid is False
        assert any(e.error_code == "COMPLIANCE_LOCK_VIOLATION" for e in result.errors)

    def test_cmmc_l2_trust_level_enforced(self, validation_service, admin_context):
        """Test CMMC L2 enforces minimum trust level."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            min_context_trust=TrustLevel.ALL,  # Below CMMC L2's MEDIUM requirement
            compliance_profile=ComplianceProfile.CMMC_L2,
        )
        context = ValidationContext(
            user_id="test-user",
            tenant_id="test-tenant",
            is_admin=True,
            active_compliance_profile=ComplianceProfile.CMMC_L2,
        )
        result = validation_service.validate_configuration(config, context)
        assert result.valid is False
        assert any(e.error_code == "COMPLIANCE_LOCK_VIOLATION" for e in result.errors)
        assert any(e.field == "min_context_trust" for e in result.errors)

    def test_fedramp_high_verbosity_enforced(self, validation_service, fedramp_context):
        """Test FedRAMP High enforces minimum verbosity."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            explanation_verbosity=Verbosity.MINIMAL,  # Below FedRAMP's DETAILED requirement
            compliance_profile=ComplianceProfile.FEDRAMP_HIGH,
        )
        result = validation_service.validate_configuration(config, fedramp_context)
        assert result.valid is False
        assert any(e.error_code == "COMPLIANCE_LOCK_VIOLATION" for e in result.errors)
        assert any(e.field == "explanation_verbosity" for e in result.errors)

    def test_cmmc_credential_tool_demotion_blocked(
        self, validation_service, admin_context
    ):
        """Test CMMC blocks demoting credential tools."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            compliance_profile=ComplianceProfile.CMMC_L2,
            tool_tier_overrides={
                "credential_manager": ToolTier.SAFE
            },  # Demoted below CRITICAL
        )
        context = ValidationContext(
            user_id="test-user",
            tenant_id="test-tenant",
            is_admin=True,
            active_compliance_profile=ComplianceProfile.CMMC_L2,
        )
        result = validation_service.validate_configuration(config, context)
        assert result.valid is False
        assert any(e.error_code == "COMPLIANCE_LOCK_VIOLATION" for e in result.errors)

    def test_no_compliance_profile_allows_lower_values(
        self, validation_service, admin_context
    ):
        """Test no compliance profile allows lower values within platform limits."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            audit_retention_days=90,
            min_context_trust=TrustLevel.ALL,
            explanation_verbosity=Verbosity.MINIMAL,
            compliance_profile=ComplianceProfile.NONE,
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is True


class TestSettingBoundsValidation:
    """Tests for setting bounds validation."""

    def test_valid_threat_pattern(
        self, validation_service, admin_context, sample_threat_pattern
    ):
        """Test valid threat pattern passes validation."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            custom_threat_patterns=[sample_threat_pattern],
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is True

    def test_empty_pattern_regex_fails(self, validation_service, admin_context):
        """Test empty pattern regex fails validation."""
        pattern = ThreatPattern(
            pattern_id="test-pattern",
            pattern_name="Test Pattern",
            pattern_regex="",  # Empty regex
            description="Test description",
        )
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            custom_threat_patterns=[pattern],
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is False
        assert any(e.error_code == "INVALID_VALUE" for e in result.errors)

    def test_invalid_severity_fails(self, validation_service, admin_context):
        """Test invalid severity fails validation."""
        pattern = ThreatPattern(
            pattern_id="test-pattern",
            pattern_name="Test Pattern",
            pattern_regex="test",
            description="Test description",
            severity="invalid_severity",  # Invalid severity
        )
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            custom_threat_patterns=[pattern],
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is False
        assert any(e.error_code == "INVALID_VALUE" for e in result.errors)


class TestPermissionValidation:
    """Tests for permission-based validation."""

    def test_admin_can_modify_threat_patterns(
        self, validation_service, admin_context, sample_threat_pattern
    ):
        """Test admin can modify threat patterns."""
        current_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            custom_threat_patterns=[],
        )
        admin_context.current_config = current_config

        new_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            custom_threat_patterns=[sample_threat_pattern],
        )
        result = validation_service.validate_configuration(new_config, admin_context)
        assert result.valid is True

    def test_non_admin_cannot_modify_threat_patterns(
        self, validation_service, user_context, sample_threat_pattern
    ):
        """Test non-admin cannot modify threat patterns."""
        current_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            custom_threat_patterns=[],
        )
        user_context.current_config = current_config

        new_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            custom_threat_patterns=[sample_threat_pattern],
        )
        result = validation_service.validate_configuration(new_config, user_context)
        assert result.valid is False
        assert any(e.error_code == "PERMISSION_DENIED" for e in result.errors)
        assert any(e.field == "custom_threat_patterns" for e in result.errors)

    def test_non_admin_cannot_modify_trust_weight_adjustments(
        self, validation_service, user_context
    ):
        """Test non-admin cannot modify trust weight adjustments."""
        current_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            trust_weight_adjustments={},
        )
        user_context.current_config = current_config

        new_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            trust_weight_adjustments={"internal": 0.1},
        )
        result = validation_service.validate_configuration(new_config, user_context)
        assert result.valid is False
        assert any(e.error_code == "PERMISSION_DENIED" for e in result.errors)
        assert any(e.field == "trust_weight_adjustments" for e in result.errors)

    def test_non_admin_cannot_modify_tool_tier_overrides(
        self, validation_service, user_context
    ):
        """Test non-admin cannot modify tool tier overrides."""
        current_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            tool_tier_overrides={},
        )
        user_context.current_config = current_config

        new_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            tool_tier_overrides={"test_tool": ToolTier.SAFE},
        )
        result = validation_service.validate_configuration(new_config, user_context)
        assert result.valid is False
        assert any(e.error_code == "PERMISSION_DENIED" for e in result.errors)

    def test_non_admin_cannot_modify_compliance_profile(
        self, validation_service, user_context
    ):
        """Test non-admin cannot modify compliance profile."""
        current_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            compliance_profile=ComplianceProfile.NONE,
        )
        user_context.current_config = current_config

        new_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            compliance_profile=ComplianceProfile.SOC2,
        )
        result = validation_service.validate_configuration(new_config, user_context)
        assert result.valid is False
        assert any(e.error_code == "PERMISSION_DENIED" for e in result.errors)

    def test_non_admin_can_modify_non_restricted_settings(
        self, validation_service, user_context
    ):
        """Test non-admin can modify non-restricted settings."""
        current_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            security_profile=SecurityProfile.BALANCED,
        )
        user_context.current_config = current_config

        new_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            security_profile=SecurityProfile.CONSERVATIVE,
        )
        result = validation_service.validate_configuration(new_config, user_context)
        assert result.valid is True


class TestSettingCombinationValidation:
    """Tests for setting combination warnings."""

    def test_risky_combination_warning(self, validation_service, admin_context):
        """Test risky combination generates warning."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            security_profile=SecurityProfile.AGGRESSIVE,
            hitl_sensitivity=HITLSensitivity.CRITICAL_ONLY,
            min_context_trust=TrustLevel.ALL,
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is True  # Still valid, just warning
        assert len(result.warnings) > 0
        assert any(w.error_code == "RISKY_COMBINATION" for w in result.warnings)

    def test_profile_mismatch_warning(self, validation_service, admin_context):
        """Test profile mismatch generates warning."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            security_profile=SecurityProfile.CONSERVATIVE,
            hitl_sensitivity=HITLSensitivity.CRITICAL_ONLY,  # Mismatched for conservative
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is True
        assert any(w.error_code == "PROFILE_MISMATCH" for w in result.warnings)

    def test_matching_profile_no_warning(self, validation_service, admin_context):
        """Test matching profile does not generate warning."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            security_profile=SecurityProfile.CONSERVATIVE,
            hitl_sensitivity=HITLSensitivity.LOW,  # Matches conservative default
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is True
        assert not any(w.error_code == "PROFILE_MISMATCH" for w in result.warnings)


class TestEffectiveConfig:
    """Tests for effective configuration generation."""

    def test_effective_config_returned_on_success(
        self, validation_service, balanced_config, admin_context
    ):
        """Test effective config is returned on successful validation."""
        result = validation_service.validate_configuration(
            balanced_config, admin_context
        )
        assert result.valid is True
        assert result.effective_config is not None
        assert result.effective_config == balanced_config

    def test_effective_config_not_returned_on_failure(
        self, validation_service, admin_context
    ):
        """Test effective config is not returned on validation failure."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            audit_retention_days=30,  # Invalid
        )
        result = validation_service.validate_configuration(config, admin_context)
        assert result.valid is False
        assert result.effective_config is None


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_validation_service_returns_same_instance(self):
        """Test singleton returns same instance."""
        service1 = get_validation_service()
        service2 = get_validation_service()
        assert service1 is service2
