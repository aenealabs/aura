"""
Project Aura - Guardrail Configuration Package

Provides user-configurable guardrail settings with compliance profile support.
Implements ADR-069 Guardrail Configuration UI.

Components:
- contracts: Data contracts and enums for configuration
- compliance_profiles: Compliance profile definitions (SOC2, CMMC, FedRAMP)
- validation_service: Configuration validation against rules
- config_service: Configuration CRUD operations with audit logging
"""

from .compliance_profiles import (
    COMPLIANCE_PROFILES,
    ComplianceProfileSpec,
    get_compliance_profile,
    get_hitl_requirements,
    get_minimum_audit_retention,
    get_minimum_trust_level,
    get_minimum_verbosity,
    is_setting_locked,
    list_compliance_profiles,
)
from .config_service import (
    GuardrailConfigurationService,
    get_config_service,
    reset_config_service,
)
from .contracts import (
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
)
from .validation_service import (
    GuardrailValidationService,
    ValidationContext,
    get_validation_service,
    reset_validation_service,
)

__all__ = [
    # Contracts - Enums
    "SecurityProfile",
    "HITLSensitivity",
    "TrustLevel",
    "Verbosity",
    "ReviewerType",
    "ComplianceProfile",
    "ToolTier",
    # Contracts - Dataclasses
    "ToolGrant",
    "ThreatPattern",
    "GuardrailConfiguration",
    "ConfigurationChangeRecord",
    "ValidationError",
    "ValidationResult",
    # Contracts - Constants
    "SECURITY_PROFILE_SPECS",
    "PLATFORM_MINIMUMS",
    # Compliance Profiles
    "ComplianceProfileSpec",
    "COMPLIANCE_PROFILES",
    "get_compliance_profile",
    "list_compliance_profiles",
    "get_hitl_requirements",
    "get_minimum_trust_level",
    "get_minimum_audit_retention",
    "get_minimum_verbosity",
    "is_setting_locked",
    # Validation Service
    "ValidationContext",
    "GuardrailValidationService",
    "get_validation_service",
    "reset_validation_service",
    # Configuration Service
    "GuardrailConfigurationService",
    "get_config_service",
    "reset_config_service",
]
