"""
Tests for guardrail configuration contracts (ADR-069).
"""

from datetime import datetime, timedelta, timezone

from src.services.guardrail_config import (
    PLATFORM_MINIMUMS,
    SECURITY_PROFILE_SPECS,
    ComplianceProfile,
    ConfigurationChangeRecord,
    GuardrailConfiguration,
    HITLSensitivity,
    ReviewerType,
    SecurityProfile,
    ToolGrant,
    ToolTier,
    TrustLevel,
    ValidationError,
    ValidationResult,
    Verbosity,
)


class TestEnums:
    """Tests for enum definitions."""

    def test_security_profile_values(self):
        """Test security profile enum values."""
        assert SecurityProfile.CONSERVATIVE.value == "conservative"
        assert SecurityProfile.BALANCED.value == "balanced"
        assert SecurityProfile.EFFICIENT.value == "efficient"
        assert SecurityProfile.AGGRESSIVE.value == "aggressive"

    def test_hitl_sensitivity_values(self):
        """Test HITL sensitivity enum values."""
        assert HITLSensitivity.LOW.value == "low"
        assert HITLSensitivity.MEDIUM.value == "medium"
        assert HITLSensitivity.HIGH.value == "high"
        assert HITLSensitivity.CRITICAL_ONLY.value == "critical_only"

    def test_trust_level_values(self):
        """Test trust level enum values."""
        assert TrustLevel.HIGH.value == "high"
        assert TrustLevel.MEDIUM.value == "medium"
        assert TrustLevel.LOW.value == "low"
        assert TrustLevel.ALL.value == "all"

    def test_trust_level_comparison(self):
        """Test trust level comparison operators."""
        assert TrustLevel.HIGH > TrustLevel.MEDIUM
        assert TrustLevel.MEDIUM > TrustLevel.LOW
        assert TrustLevel.LOW > TrustLevel.ALL
        assert TrustLevel.HIGH >= TrustLevel.HIGH
        assert TrustLevel.ALL <= TrustLevel.LOW
        assert not (TrustLevel.LOW > TrustLevel.HIGH)

    def test_verbosity_values(self):
        """Test verbosity enum values."""
        assert Verbosity.MINIMAL.value == "minimal"
        assert Verbosity.STANDARD.value == "standard"
        assert Verbosity.DETAILED.value == "detailed"
        assert Verbosity.DEBUG.value == "debug"

    def test_reviewer_type_values(self):
        """Test reviewer type enum values."""
        assert ReviewerType.SELF.value == "self"
        assert ReviewerType.TEAM_LEAD.value == "team_lead"
        assert ReviewerType.SECURITY_TEAM.value == "security_team"

    def test_compliance_profile_values(self):
        """Test compliance profile enum values."""
        assert ComplianceProfile.NONE.value == "none"
        assert ComplianceProfile.SOC2.value == "soc2"
        assert ComplianceProfile.CMMC_L2.value == "cmmc_l2"
        assert ComplianceProfile.CMMC_L3.value == "cmmc_l3"
        assert ComplianceProfile.FEDRAMP_MODERATE.value == "fedramp_moderate"
        assert ComplianceProfile.FEDRAMP_HIGH.value == "fedramp_high"

    def test_tool_tier_values(self):
        """Test tool tier enum values."""
        assert ToolTier.SAFE.value == "safe"
        assert ToolTier.MONITORING.value == "monitoring"
        assert ToolTier.DANGEROUS.value == "dangerous"
        assert ToolTier.CRITICAL.value == "critical"


class TestToolGrant:
    """Tests for ToolGrant dataclass."""

    def test_tool_grant_creation(self, sample_tool_grant):
        """Test tool grant creation."""
        assert sample_tool_grant.tool_name == "deploy_production"
        assert sample_tool_grant.granted_tier == ToolTier.CRITICAL
        assert sample_tool_grant.granted_by == "admin-user"
        assert (
            sample_tool_grant.justification
            == "Production deployment access for release"
        )

    def test_tool_grant_not_expired_without_expiry(self, sample_tool_grant):
        """Test tool grant without expiry is not expired."""
        assert sample_tool_grant.expires_at is None
        assert not sample_tool_grant.is_expired()

    def test_tool_grant_not_expired_with_future_expiry(self):
        """Test tool grant with future expiry is not expired."""
        grant = ToolGrant(
            tool_name="test_tool",
            granted_tier=ToolTier.MONITORING,
            granted_by="admin",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        assert not grant.is_expired()

    def test_tool_grant_expired_with_past_expiry(self):
        """Test tool grant with past expiry is expired."""
        grant = ToolGrant(
            tool_name="test_tool",
            granted_tier=ToolTier.MONITORING,
            granted_by="admin",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert grant.is_expired()

    def test_tool_grant_to_dict(self, sample_tool_grant):
        """Test tool grant serialization."""
        data = sample_tool_grant.to_dict()
        assert data["tool_name"] == "deploy_production"
        assert data["granted_tier"] == "critical"
        assert data["granted_by"] == "admin-user"
        assert "granted_at" in data
        assert data["expires_at"] is None


class TestThreatPattern:
    """Tests for ThreatPattern dataclass."""

    def test_threat_pattern_creation(self, sample_threat_pattern):
        """Test threat pattern creation."""
        assert sample_threat_pattern.pattern_id == "test-pattern-001"
        assert sample_threat_pattern.pattern_name == "Test SQL Injection"
        assert "SELECT" in sample_threat_pattern.pattern_regex
        assert sample_threat_pattern.severity == "high"
        assert sample_threat_pattern.enabled is True

    def test_threat_pattern_to_dict(self, sample_threat_pattern):
        """Test threat pattern serialization."""
        data = sample_threat_pattern.to_dict()
        assert data["pattern_id"] == "test-pattern-001"
        assert data["pattern_name"] == "Test SQL Injection"
        assert data["severity"] == "high"
        assert data["enabled"] is True
        assert "created_at" in data


class TestGuardrailConfiguration:
    """Tests for GuardrailConfiguration dataclass."""

    def test_default_configuration(self, default_config):
        """Test default configuration values."""
        assert default_config.security_profile == SecurityProfile.BALANCED
        assert default_config.hitl_sensitivity == HITLSensitivity.MEDIUM
        assert default_config.min_context_trust == TrustLevel.MEDIUM
        assert default_config.explanation_verbosity == Verbosity.STANDARD
        assert default_config.quarantine_reviewer == ReviewerType.TEAM_LEAD
        assert default_config.audit_retention_days == 365
        assert default_config.compliance_profile == ComplianceProfile.NONE

    def test_configuration_to_dict(self, default_config):
        """Test configuration serialization."""
        data = default_config.to_dict()
        assert data["security_profile"] == "balanced"
        assert data["hitl_sensitivity"] == "medium"
        assert data["min_context_trust"] == "medium"
        assert data["audit_retention_days"] == 365

    def test_configuration_from_dict(self, default_config):
        """Test configuration deserialization."""
        data = default_config.to_dict()
        restored = GuardrailConfiguration.from_dict(data)
        assert restored.security_profile == default_config.security_profile
        assert restored.hitl_sensitivity == default_config.hitl_sensitivity
        assert restored.min_context_trust == default_config.min_context_trust
        assert restored.audit_retention_days == default_config.audit_retention_days

    def test_configuration_with_tool_grants(self, sample_tool_grant):
        """Test configuration with project tool grants."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            project_tool_grants={"project-1": [sample_tool_grant]},
        )
        assert "project-1" in config.project_tool_grants
        assert len(config.project_tool_grants["project-1"]) == 1

    def test_configuration_with_threat_patterns(self, sample_threat_pattern):
        """Test configuration with custom threat patterns."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            custom_threat_patterns=[sample_threat_pattern],
        )
        assert len(config.custom_threat_patterns) == 1
        assert config.custom_threat_patterns[0].pattern_id == "test-pattern-001"

    def test_configuration_roundtrip(self, config_with_overrides):
        """Test configuration serialization roundtrip."""
        data = config_with_overrides.to_dict()
        restored = GuardrailConfiguration.from_dict(data)
        assert restored.tool_tier_overrides == config_with_overrides.tool_tier_overrides
        assert (
            restored.trust_weight_adjustments
            == config_with_overrides.trust_weight_adjustments
        )


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_validation_error_creation(self):
        """Test validation error creation."""
        error = ValidationError(
            field="audit_retention_days",
            message="Must be at least 90 days",
            error_code="PLATFORM_MINIMUM_VIOLATION",
        )
        assert error.field == "audit_retention_days"
        assert error.severity == "error"

    def test_validation_error_warning(self):
        """Test validation warning creation."""
        warning = ValidationError(
            field="hitl_sensitivity",
            message="Consider increasing sensitivity",
            error_code="RECOMMENDATION",
            severity="warning",
        )
        assert warning.severity == "warning"

    def test_validation_error_to_dict(self):
        """Test validation error serialization."""
        error = ValidationError(
            field="test_field",
            message="Test message",
            error_code="TEST_CODE",
        )
        data = error.to_dict()
        assert data["field"] == "test_field"
        assert data["message"] == "Test message"
        assert data["error_code"] == "TEST_CODE"
        assert data["severity"] == "error"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self, default_config):
        """Test valid result creation."""
        result = ValidationResult(
            valid=True,
            errors=[],
            warnings=[],
            effective_config=default_config,
        )
        assert result.valid is True
        assert len(result.errors) == 0
        assert result.effective_config is not None

    def test_invalid_result(self):
        """Test invalid result with errors."""
        error = ValidationError(
            field="test",
            message="Test error",
            error_code="TEST",
        )
        result = ValidationResult(
            valid=False,
            errors=[error],
        )
        assert result.valid is False
        assert len(result.errors) == 1

    def test_result_with_warnings(self, default_config):
        """Test result with warnings but still valid."""
        warning = ValidationError(
            field="test",
            message="Test warning",
            error_code="TEST",
            severity="warning",
        )
        result = ValidationResult(
            valid=True,
            warnings=[warning],
            effective_config=default_config,
        )
        assert result.valid is True
        assert len(result.warnings) == 1

    def test_result_to_dict(self, default_config):
        """Test result serialization."""
        result = ValidationResult(
            valid=True,
            effective_config=default_config,
        )
        data = result.to_dict()
        assert data["valid"] is True
        assert data["errors"] == []
        assert data["effective_config"] is not None


class TestConfigurationChangeRecord:
    """Tests for ConfigurationChangeRecord dataclass."""

    def test_change_record_creation(self):
        """Test change record creation."""
        record = ConfigurationChangeRecord(
            record_id="test-record-001",
            timestamp=datetime.now(timezone.utc),
            user_id="test-user",
            tenant_id="test-tenant",
            setting_path="security_profile",
            previous_value="balanced",
            new_value="conservative",
            justification="Security hardening",
        )
        assert record.record_id == "test-record-001"
        assert record.setting_path == "security_profile"
        assert record.change_type == "update"

    def test_change_record_to_dict(self):
        """Test change record serialization."""
        record = ConfigurationChangeRecord(
            record_id="test-record-001",
            timestamp=datetime.now(timezone.utc),
            user_id="test-user",
            tenant_id="test-tenant",
            setting_path="audit_retention_days",
            previous_value=365,
            new_value=730,
            justification="Compliance requirement",
            change_type="update",
        )
        data = record.to_dict()
        assert data["record_id"] == "test-record-001"
        assert data["setting_path"] == "audit_retention_days"
        assert data["previous_value"] == 365
        assert data["new_value"] == 730


class TestSecurityProfileSpecs:
    """Tests for security profile specifications."""

    def test_conservative_spec(self):
        """Test conservative profile specification."""
        spec = SECURITY_PROFILE_SPECS[SecurityProfile.CONSERVATIVE]
        assert spec["hitl_threshold"] == HITLSensitivity.LOW
        assert spec["context_trust"] == TrustLevel.HIGH
        assert spec["explanation"] == Verbosity.DETAILED

    def test_balanced_spec(self):
        """Test balanced profile specification."""
        spec = SECURITY_PROFILE_SPECS[SecurityProfile.BALANCED]
        assert spec["hitl_threshold"] == HITLSensitivity.MEDIUM
        assert spec["context_trust"] == TrustLevel.MEDIUM
        assert spec["explanation"] == Verbosity.STANDARD

    def test_efficient_spec(self):
        """Test efficient profile specification."""
        spec = SECURITY_PROFILE_SPECS[SecurityProfile.EFFICIENT]
        assert spec["hitl_threshold"] == HITLSensitivity.HIGH
        assert ToolTier.MONITORING in spec["auto_approve_tiers"]

    def test_aggressive_spec(self):
        """Test aggressive profile specification."""
        spec = SECURITY_PROFILE_SPECS[SecurityProfile.AGGRESSIVE]
        assert spec["hitl_threshold"] == HITLSensitivity.CRITICAL_ONLY
        assert spec["context_trust"] == TrustLevel.LOW
        assert ToolTier.DANGEROUS in spec["auto_approve_tiers"]


class TestPlatformMinimums:
    """Tests for platform minimum thresholds."""

    def test_audit_retention_minimums(self):
        """Test audit retention platform minimums."""
        assert PLATFORM_MINIMUMS["min_audit_retention_days"] == 90
        assert PLATFORM_MINIMUMS["max_audit_retention_days"] == 2555

    def test_trust_weight_adjustments(self):
        """Test trust weight adjustment bounds."""
        assert PLATFORM_MINIMUMS["trust_weight_min_adjustment"] == -0.15
        assert PLATFORM_MINIMUMS["trust_weight_max_adjustment"] == 0.15

    def test_required_features(self):
        """Test required features are enabled."""
        assert PLATFORM_MINIMUMS["hitl_required_for_critical"] is True
        assert PLATFORM_MINIMUMS["threat_detection_always_active"] is True
        assert PLATFORM_MINIMUMS["trust_verification_always_active"] is True
        assert PLATFORM_MINIMUMS["explanation_generation_always_active"] is True
