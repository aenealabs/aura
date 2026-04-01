"""
Shared fixtures for guardrail configuration tests.
"""

import pytest

from src.services.guardrail_config import (
    ComplianceProfile,
    GuardrailConfiguration,
    HITLSensitivity,
    SecurityProfile,
    ThreatPattern,
    ToolGrant,
    ToolTier,
    TrustLevel,
    ValidationContext,
    Verbosity,
    get_config_service,
    get_validation_service,
    reset_config_service,
    reset_validation_service,
)


@pytest.fixture(autouse=True)
def reset_services():
    """Reset singleton services before each test."""
    reset_config_service()
    reset_validation_service()
    yield
    reset_config_service()
    reset_validation_service()


@pytest.fixture
def validation_service():
    """Get validation service instance."""
    return get_validation_service()


@pytest.fixture
def config_service():
    """Get configuration service instance."""
    return get_config_service()


@pytest.fixture
def default_config() -> GuardrailConfiguration:
    """Create a default configuration."""
    return GuardrailConfiguration(
        tenant_id="test-tenant",
        user_id="test-user",
    )


@pytest.fixture
def balanced_config() -> GuardrailConfiguration:
    """Create a balanced security profile configuration."""
    return GuardrailConfiguration(
        tenant_id="test-tenant",
        user_id="test-user",
        security_profile=SecurityProfile.BALANCED,
        hitl_sensitivity=HITLSensitivity.MEDIUM,
        min_context_trust=TrustLevel.MEDIUM,
        explanation_verbosity=Verbosity.STANDARD,
        audit_retention_days=365,
    )


@pytest.fixture
def conservative_config() -> GuardrailConfiguration:
    """Create a conservative security profile configuration."""
    return GuardrailConfiguration(
        tenant_id="test-tenant",
        user_id="test-user",
        security_profile=SecurityProfile.CONSERVATIVE,
        hitl_sensitivity=HITLSensitivity.LOW,
        min_context_trust=TrustLevel.HIGH,
        explanation_verbosity=Verbosity.DETAILED,
        audit_retention_days=730,
    )


@pytest.fixture
def aggressive_config() -> GuardrailConfiguration:
    """Create an aggressive security profile configuration."""
    return GuardrailConfiguration(
        tenant_id="test-tenant",
        user_id="test-user",
        security_profile=SecurityProfile.AGGRESSIVE,
        hitl_sensitivity=HITLSensitivity.CRITICAL_ONLY,
        min_context_trust=TrustLevel.ALL,
        explanation_verbosity=Verbosity.MINIMAL,
        audit_retention_days=90,
    )


@pytest.fixture
def soc2_config() -> GuardrailConfiguration:
    """Create a SOC2-compliant configuration."""
    return GuardrailConfiguration(
        tenant_id="test-tenant",
        user_id="test-user",
        security_profile=SecurityProfile.BALANCED,
        hitl_sensitivity=HITLSensitivity.MEDIUM,
        min_context_trust=TrustLevel.MEDIUM,
        explanation_verbosity=Verbosity.STANDARD,
        audit_retention_days=365,
        compliance_profile=ComplianceProfile.SOC2,
    )


@pytest.fixture
def cmmc_l2_config() -> GuardrailConfiguration:
    """Create a CMMC Level 2-compliant configuration."""
    return GuardrailConfiguration(
        tenant_id="test-tenant",
        user_id="test-user",
        security_profile=SecurityProfile.BALANCED,
        hitl_sensitivity=HITLSensitivity.MEDIUM,
        min_context_trust=TrustLevel.MEDIUM,
        explanation_verbosity=Verbosity.STANDARD,
        audit_retention_days=365,
        compliance_profile=ComplianceProfile.CMMC_L2,
    )


@pytest.fixture
def fedramp_high_config() -> GuardrailConfiguration:
    """Create a FedRAMP High-compliant configuration."""
    return GuardrailConfiguration(
        tenant_id="test-tenant",
        user_id="test-user",
        security_profile=SecurityProfile.CONSERVATIVE,
        hitl_sensitivity=HITLSensitivity.LOW,
        min_context_trust=TrustLevel.HIGH,
        explanation_verbosity=Verbosity.DETAILED,
        audit_retention_days=2555,
        compliance_profile=ComplianceProfile.FEDRAMP_HIGH,
    )


@pytest.fixture
def admin_context() -> ValidationContext:
    """Create an admin validation context."""
    return ValidationContext(
        user_id="admin-user",
        tenant_id="test-tenant",
        is_admin=True,
    )


@pytest.fixture
def user_context() -> ValidationContext:
    """Create a non-admin validation context."""
    return ValidationContext(
        user_id="regular-user",
        tenant_id="test-tenant",
        is_admin=False,
    )


@pytest.fixture
def soc2_context() -> ValidationContext:
    """Create a SOC2 compliance context."""
    return ValidationContext(
        user_id="test-user",
        tenant_id="test-tenant",
        is_admin=True,
        active_compliance_profile=ComplianceProfile.SOC2,
    )


@pytest.fixture
def fedramp_context() -> ValidationContext:
    """Create a FedRAMP compliance context."""
    return ValidationContext(
        user_id="test-user",
        tenant_id="test-tenant",
        is_admin=True,
        active_compliance_profile=ComplianceProfile.FEDRAMP_HIGH,
    )


@pytest.fixture
def sample_threat_pattern() -> ThreatPattern:
    """Create a sample threat pattern."""
    return ThreatPattern(
        pattern_id="test-pattern-001",
        pattern_name="Test SQL Injection",
        pattern_regex=r"(?:SELECT|INSERT|UPDATE|DELETE).*(?:FROM|INTO|SET)",
        description="Detects potential SQL injection patterns",
        severity="high",
        created_by="admin-user",
    )


@pytest.fixture
def sample_tool_grant() -> ToolGrant:
    """Create a sample tool grant."""
    return ToolGrant(
        tool_name="deploy_production",
        granted_tier=ToolTier.CRITICAL,
        granted_by="admin-user",
        justification="Production deployment access for release",
    )


@pytest.fixture
def config_with_patterns(sample_threat_pattern) -> GuardrailConfiguration:
    """Create a configuration with custom threat patterns."""
    return GuardrailConfiguration(
        tenant_id="test-tenant",
        user_id="test-user",
        custom_threat_patterns=[sample_threat_pattern],
    )


@pytest.fixture
def config_with_overrides() -> GuardrailConfiguration:
    """Create a configuration with tool tier overrides."""
    return GuardrailConfiguration(
        tenant_id="test-tenant",
        user_id="test-user",
        tool_tier_overrides={
            "read_file": ToolTier.SAFE,
            "write_file": ToolTier.MONITORING,
            "execute_command": ToolTier.DANGEROUS,
        },
        trust_weight_adjustments={
            "internal_repo": 0.1,
            "external_repo": -0.1,
        },
    )
