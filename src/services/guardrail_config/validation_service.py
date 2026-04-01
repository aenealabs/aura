"""
Project Aura - Guardrail Configuration Validation Service

Validates configuration changes against platform minimums and compliance profiles.
Implements ADR-069 Guardrail Configuration UI.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .compliance_profiles import (
    COMPLIANCE_PROFILES,
    get_compliance_profile,
    get_minimum_audit_retention,
    get_minimum_trust_level,
    get_minimum_verbosity,
)
from .contracts import (
    PLATFORM_MINIMUMS,
    SECURITY_PROFILE_SPECS,
    ComplianceProfile,
    GuardrailConfiguration,
    HITLSensitivity,
    ToolTier,
    TrustLevel,
    ValidationError,
    ValidationResult,
    Verbosity,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationContext:
    """Context for configuration validation."""

    user_id: str
    tenant_id: str
    is_admin: bool = False
    active_compliance_profile: ComplianceProfile = ComplianceProfile.NONE
    current_config: Optional[GuardrailConfiguration] = None


class GuardrailValidationService:
    """
    Validates guardrail configuration changes.

    Enforces:
    1. Platform minimum thresholds
    2. Compliance profile locks
    3. Setting bounds and combinations
    4. Permission levels (admin-only settings)
    """

    def __init__(self):
        """Initialize the validation service."""
        self._platform_minimums = PLATFORM_MINIMUMS
        self._compliance_profiles = COMPLIANCE_PROFILES

    def validate_configuration(
        self,
        config: GuardrailConfiguration,
        context: ValidationContext,
    ) -> ValidationResult:
        """
        Validate a configuration against all rules.

        Args:
            config: Configuration to validate
            context: Validation context

        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []

        # 1. Enforce platform minimums
        platform_errors = self._validate_platform_minimums(config)
        errors.extend(platform_errors)

        # 2. Apply compliance profile locks
        compliance_errors = self._validate_compliance_profile(config, context)
        errors.extend(compliance_errors)

        # 3. Validate setting bounds
        bounds_errors = self._validate_setting_bounds(config)
        errors.extend(bounds_errors)

        # 4. Check permission levels
        permission_errors = self._validate_permissions(config, context)
        errors.extend(permission_errors)

        # 5. Validate setting combinations
        combo_warnings = self._validate_setting_combinations(config)
        warnings.extend(combo_warnings)

        # Create effective config (with adjustments applied)
        effective_config = (
            self._apply_adjustments(config, context) if not errors else None
        )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            effective_config=effective_config,
        )

    def _validate_platform_minimums(
        self, config: GuardrailConfiguration
    ) -> list[ValidationError]:
        """Validate against platform minimum thresholds."""
        errors: list[ValidationError] = []

        # Audit retention minimum
        min_retention = self._platform_minimums["min_audit_retention_days"]
        max_retention = self._platform_minimums["max_audit_retention_days"]

        if config.audit_retention_days < min_retention:
            errors.append(
                ValidationError(
                    field="audit_retention_days",
                    message=f"Audit retention must be at least {min_retention} days",
                    error_code="PLATFORM_MINIMUM_VIOLATION",
                )
            )
        elif config.audit_retention_days > max_retention:
            errors.append(
                ValidationError(
                    field="audit_retention_days",
                    message=f"Audit retention cannot exceed {max_retention} days",
                    error_code="PLATFORM_MAXIMUM_VIOLATION",
                )
            )

        # Trust weight adjustments
        min_adj = self._platform_minimums["trust_weight_min_adjustment"]
        max_adj = self._platform_minimums["trust_weight_max_adjustment"]

        for source, adjustment in config.trust_weight_adjustments.items():
            if adjustment < min_adj or adjustment > max_adj:
                errors.append(
                    ValidationError(
                        field=f"trust_weight_adjustments.{source}",
                        message=f"Trust weight adjustment must be between {min_adj} and {max_adj}",
                        error_code="PLATFORM_BOUNDS_VIOLATION",
                    )
                )

        return errors

    def _validate_compliance_profile(
        self,
        config: GuardrailConfiguration,
        context: ValidationContext,
    ) -> list[ValidationError]:
        """Validate against active compliance profile locks."""
        errors: list[ValidationError] = []

        # Use config's compliance profile or context's active profile
        active_profile = config.compliance_profile
        if active_profile == ComplianceProfile.NONE:
            active_profile = context.active_compliance_profile

        if active_profile == ComplianceProfile.NONE:
            return errors

        profile_spec = get_compliance_profile(active_profile)
        if not profile_spec:
            return errors

        # Check minimum trust level
        min_trust = get_minimum_trust_level(active_profile)
        if min_trust and config.min_context_trust < min_trust:
            errors.append(
                ValidationError(
                    field="min_context_trust",
                    message=f"Compliance profile {active_profile.value} requires minimum trust level {min_trust.value}",
                    error_code="COMPLIANCE_LOCK_VIOLATION",
                )
            )

        # Check minimum audit retention
        min_retention = get_minimum_audit_retention(active_profile)
        if min_retention and config.audit_retention_days < min_retention:
            errors.append(
                ValidationError(
                    field="audit_retention_days",
                    message=f"Compliance profile {active_profile.value} requires minimum {min_retention} days retention",
                    error_code="COMPLIANCE_LOCK_VIOLATION",
                )
            )

        # Check minimum verbosity
        min_verbosity = get_minimum_verbosity(active_profile)
        if min_verbosity:
            verbosity_order = {
                Verbosity.MINIMAL: 0,
                Verbosity.STANDARD: 1,
                Verbosity.DETAILED: 2,
                Verbosity.DEBUG: 3,
            }
            if (
                verbosity_order[config.explanation_verbosity]
                < verbosity_order[min_verbosity]
            ):
                errors.append(
                    ValidationError(
                        field="explanation_verbosity",
                        message=f"Compliance profile {active_profile.value} requires minimum verbosity {min_verbosity.value}",
                        error_code="COMPLIANCE_LOCK_VIOLATION",
                    )
                )

        # Check tool tier overrides (can only promote, not demote)
        if profile_spec.credential_tool_tier:
            for tool_name, tier in config.tool_tier_overrides.items():
                if "credential" in tool_name.lower() or "secret" in tool_name.lower():
                    tier_order = {
                        ToolTier.SAFE: 0,
                        ToolTier.MONITORING: 1,
                        ToolTier.DANGEROUS: 2,
                        ToolTier.CRITICAL: 3,
                    }
                    if tier_order[tier] < tier_order[profile_spec.credential_tool_tier]:
                        errors.append(
                            ValidationError(
                                field=f"tool_tier_overrides.{tool_name}",
                                message=f"Credential tools cannot be demoted below {profile_spec.credential_tool_tier.value}",
                                error_code="COMPLIANCE_LOCK_VIOLATION",
                            )
                        )

        return errors

    def _validate_setting_bounds(
        self, config: GuardrailConfiguration
    ) -> list[ValidationError]:
        """Validate setting values are within allowed bounds."""
        errors: list[ValidationError] = []

        # Validate enum values are valid (dataclass handles this, but check for safety)
        # No additional bounds checking needed for enums

        # Validate custom threat patterns
        for pattern in config.custom_threat_patterns:
            if not pattern.pattern_regex:
                errors.append(
                    ValidationError(
                        field=f"custom_threat_patterns.{pattern.pattern_id}",
                        message="Pattern regex cannot be empty",
                        error_code="INVALID_VALUE",
                    )
                )
            if pattern.severity not in ["low", "medium", "high", "critical"]:
                errors.append(
                    ValidationError(
                        field=f"custom_threat_patterns.{pattern.pattern_id}.severity",
                        message=f"Invalid severity: {pattern.severity}",
                        error_code="INVALID_VALUE",
                    )
                )

        return errors

    def _validate_permissions(
        self,
        config: GuardrailConfiguration,
        context: ValidationContext,
    ) -> list[ValidationError]:
        """Validate user has permission to modify settings."""
        errors: list[ValidationError] = []

        if not context.is_admin and context.current_config:
            # Check if admin-only settings were modified
            if (
                config.custom_threat_patterns
                != context.current_config.custom_threat_patterns
            ):
                errors.append(
                    ValidationError(
                        field="custom_threat_patterns",
                        message="Only administrators can modify custom threat patterns",
                        error_code="PERMISSION_DENIED",
                    )
                )

            if (
                config.trust_weight_adjustments
                != context.current_config.trust_weight_adjustments
            ):
                errors.append(
                    ValidationError(
                        field="trust_weight_adjustments",
                        message="Only administrators can modify trust weight adjustments",
                        error_code="PERMISSION_DENIED",
                    )
                )

            if config.tool_tier_overrides != context.current_config.tool_tier_overrides:
                errors.append(
                    ValidationError(
                        field="tool_tier_overrides",
                        message="Only administrators can modify tool tier overrides",
                        error_code="PERMISSION_DENIED",
                    )
                )

            if config.compliance_profile != context.current_config.compliance_profile:
                errors.append(
                    ValidationError(
                        field="compliance_profile",
                        message="Only administrators can modify compliance profile",
                        error_code="PERMISSION_DENIED",
                    )
                )

        return errors

    def _validate_setting_combinations(
        self, config: GuardrailConfiguration
    ) -> list[ValidationError]:
        """Validate setting combinations and generate warnings."""
        warnings: list[ValidationError] = []

        # Warn about risky combinations
        if (
            config.security_profile == config.security_profile.AGGRESSIVE
            and config.hitl_sensitivity == HITLSensitivity.CRITICAL_ONLY
            and config.min_context_trust == TrustLevel.ALL
        ):
            warnings.append(
                ValidationError(
                    field="security_profile",
                    message="Aggressive profile with minimal HITL and trust requirements significantly reduces safety",
                    error_code="RISKY_COMBINATION",
                    severity="warning",
                )
            )

        # Warn about mismatched settings
        profile_spec = SECURITY_PROFILE_SPECS.get(config.security_profile)
        if profile_spec:
            if config.hitl_sensitivity != profile_spec["hitl_threshold"]:
                warnings.append(
                    ValidationError(
                        field="hitl_sensitivity",
                        message=f"HITL sensitivity differs from {config.security_profile.value} profile default",
                        error_code="PROFILE_MISMATCH",
                        severity="warning",
                    )
                )

        return warnings

    def _apply_adjustments(
        self,
        config: GuardrailConfiguration,
        context: ValidationContext,
    ) -> GuardrailConfiguration:
        """Apply any required adjustments and return effective config."""
        # For now, return as-is (compliance enforcement happens at read time)
        # Future: could apply compliance profile defaults here
        return config


# Singleton instance
_validation_service: GuardrailValidationService | None = None


def get_validation_service() -> GuardrailValidationService:
    """Get or create the singleton validation service instance."""
    global _validation_service
    if _validation_service is None:
        _validation_service = GuardrailValidationService()
    return _validation_service


def reset_validation_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _validation_service
    _validation_service = None
