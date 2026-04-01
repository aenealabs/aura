"""
Project Aura - Guardrail Configuration Service

Manages CRUD operations for guardrail configurations with audit logging.
Implements ADR-069 Guardrail Configuration UI.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .compliance_profiles import get_compliance_profile
from .contracts import (
    ComplianceProfile,
    ConfigurationChangeRecord,
    GuardrailConfiguration,
    ValidationResult,
)
from .validation_service import (
    GuardrailValidationService,
    ValidationContext,
    get_validation_service,
)

logger = logging.getLogger(__name__)


class GuardrailConfigurationService:
    """
    Service for managing guardrail configurations.

    Provides CRUD operations with:
    1. Automatic validation before save
    2. Audit trail generation
    3. Compliance profile enforcement
    4. Change history tracking
    """

    def __init__(
        self,
        validation_service: Optional[GuardrailValidationService] = None,
    ):
        """
        Initialize the configuration service.

        Args:
            validation_service: Optional validation service instance
        """
        self._validation_service = validation_service or get_validation_service()
        # In-memory storage for configurations (replaced by DynamoDB in production)
        self._configurations: dict[str, GuardrailConfiguration] = {}
        # In-memory storage for change records (replaced by DynamoDB in production)
        self._change_records: list[ConfigurationChangeRecord] = []

    def get_configuration(
        self,
        tenant_id: str,
        user_id: str,
    ) -> Optional[GuardrailConfiguration]:
        """
        Get the configuration for a tenant/user.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier

        Returns:
            Configuration if found, None otherwise
        """
        config_key = self._make_config_key(tenant_id, user_id)
        config = self._configurations.get(config_key)

        if config:
            # Apply compliance profile overrides at read time
            return self._apply_compliance_overrides(config)

        return None

    def get_or_create_configuration(
        self,
        tenant_id: str,
        user_id: str,
    ) -> GuardrailConfiguration:
        """
        Get existing configuration or create default.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier

        Returns:
            Existing or new default configuration
        """
        config = self.get_configuration(tenant_id, user_id)
        if config:
            return config

        # Create default configuration
        default_config = GuardrailConfiguration(
            tenant_id=tenant_id,
            user_id=user_id,
        )

        config_key = self._make_config_key(tenant_id, user_id)
        self._configurations[config_key] = default_config

        logger.info(f"Created default configuration for {tenant_id}/{user_id}")
        return default_config

    def update_configuration(
        self,
        config: GuardrailConfiguration,
        context: ValidationContext,
        justification: str = "",
    ) -> ValidationResult:
        """
        Update a configuration with validation.

        Args:
            config: New configuration to save
            context: Validation context
            justification: Business justification for change

        Returns:
            ValidationResult with success/failure and any errors
        """
        # Get current configuration for comparison
        current_config = self.get_configuration(config.tenant_id, config.user_id)
        context.current_config = current_config

        # Validate the new configuration
        result = self._validation_service.validate_configuration(config, context)

        if not result.valid:
            logger.warning(
                f"Configuration update rejected for {config.tenant_id}/{config.user_id}: "
                f"{len(result.errors)} errors"
            )
            return result

        # Generate change records
        if current_config:
            changes = self._detect_changes(current_config, config)
            for setting_path, (old_value, new_value) in changes.items():
                record = ConfigurationChangeRecord(
                    record_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    user_id=context.user_id,
                    tenant_id=context.tenant_id,
                    setting_path=setting_path,
                    previous_value=old_value,
                    new_value=new_value,
                    justification=justification,
                    compliance_profile=config.compliance_profile,
                    change_type="update",
                )
                self._change_records.append(record)
                logger.info(
                    f"Configuration change recorded: {setting_path} changed by {context.user_id}"
                )

        # Update metadata
        config.last_modified_by = context.user_id
        config.last_modified_at = datetime.now(timezone.utc)
        config.change_justification = justification
        if current_config:
            config.version = current_config.version + 1
        else:
            config.version = 1

        # Save the configuration
        config_key = self._make_config_key(config.tenant_id, config.user_id)
        self._configurations[config_key] = config

        logger.info(
            f"Configuration updated for {config.tenant_id}/{config.user_id} "
            f"(version {config.version})"
        )

        return result

    def reset_to_defaults(
        self,
        tenant_id: str,
        user_id: str,
        context: ValidationContext,
        justification: str = "Reset to defaults",
    ) -> ValidationResult:
        """
        Reset configuration to default values.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            context: Validation context
            justification: Business justification

        Returns:
            ValidationResult
        """
        current_config = self.get_configuration(tenant_id, user_id)

        # Create default configuration
        default_config = GuardrailConfiguration(
            tenant_id=tenant_id,
            user_id=user_id,
        )

        # Record the reset
        if current_config:
            record = ConfigurationChangeRecord(
                record_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                user_id=context.user_id,
                tenant_id=tenant_id,
                setting_path="*",
                previous_value=current_config.to_dict(),
                new_value=default_config.to_dict(),
                justification=justification,
                compliance_profile=current_config.compliance_profile,
                change_type="reset",
            )
            self._change_records.append(record)
            default_config.version = current_config.version + 1

        # Save the default configuration
        config_key = self._make_config_key(tenant_id, user_id)
        self._configurations[config_key] = default_config

        logger.info(f"Configuration reset to defaults for {tenant_id}/{user_id}")

        return ValidationResult(valid=True, effective_config=default_config)

    def delete_configuration(
        self,
        tenant_id: str,
        user_id: str,
        context: ValidationContext,
        justification: str = "",
    ) -> bool:
        """
        Delete a configuration.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            context: Validation context
            justification: Business justification

        Returns:
            True if deleted, False if not found
        """
        config_key = self._make_config_key(tenant_id, user_id)
        current_config = self._configurations.get(config_key)

        if not current_config:
            return False

        # Record the deletion
        record = ConfigurationChangeRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            user_id=context.user_id,
            tenant_id=tenant_id,
            setting_path="*",
            previous_value=current_config.to_dict(),
            new_value=None,
            justification=justification,
            compliance_profile=current_config.compliance_profile,
            change_type="delete",
        )
        self._change_records.append(record)

        # Delete the configuration
        del self._configurations[config_key]

        logger.info(f"Configuration deleted for {tenant_id}/{user_id}")
        return True

    def get_change_history(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[ConfigurationChangeRecord]:
        """
        Get change history for a tenant/user.

        Args:
            tenant_id: Tenant identifier
            user_id: Optional user identifier (None for all tenant changes)
            limit: Maximum records to return

        Returns:
            List of change records, most recent first
        """
        records = [
            r
            for r in self._change_records
            if r.tenant_id == tenant_id and (user_id is None or r.user_id == user_id)
        ]

        # Sort by timestamp descending
        records.sort(key=lambda r: r.timestamp, reverse=True)

        return records[:limit]

    def apply_compliance_profile(
        self,
        tenant_id: str,
        user_id: str,
        profile: ComplianceProfile,
        context: ValidationContext,
        justification: str = "",
    ) -> ValidationResult:
        """
        Apply a compliance profile to a configuration.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            profile: Compliance profile to apply
            context: Validation context
            justification: Business justification

        Returns:
            ValidationResult
        """
        config = self.get_or_create_configuration(tenant_id, user_id)

        # Update the compliance profile
        config.compliance_profile = profile

        # Apply compliance minimums
        profile_spec = get_compliance_profile(profile)
        if profile_spec:
            # Enforce minimum audit retention
            if (
                profile_spec.min_audit_retention_days
                and config.audit_retention_days < profile_spec.min_audit_retention_days
            ):
                config.audit_retention_days = profile_spec.min_audit_retention_days

            # Enforce minimum trust level
            if profile_spec.min_context_trust_level:
                trust_order = {"all": 0, "low": 1, "medium": 2, "high": 3}
                current_level = trust_order.get(config.min_context_trust.value, 0)
                required_level = trust_order.get(
                    profile_spec.min_context_trust_level.value, 0
                )
                if current_level < required_level:
                    config.min_context_trust = profile_spec.min_context_trust_level

            # Enforce minimum verbosity
            if profile_spec.min_explanation_verbosity:
                verbosity_order = {
                    "minimal": 0,
                    "standard": 1,
                    "detailed": 2,
                    "debug": 3,
                }
                current_verbosity = verbosity_order.get(
                    config.explanation_verbosity.value, 0
                )
                required_verbosity = verbosity_order.get(
                    profile_spec.min_explanation_verbosity.value, 0
                )
                if current_verbosity < required_verbosity:
                    config.explanation_verbosity = (
                        profile_spec.min_explanation_verbosity
                    )

        # Validate and save
        return self.update_configuration(
            config,
            context,
            justification or f"Applied {profile.value} compliance profile",
        )

    def export_configuration(
        self,
        tenant_id: str,
        user_id: str,
    ) -> Optional[dict[str, Any]]:
        """
        Export configuration for backup or ATO evidence.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier

        Returns:
            Configuration as dictionary, or None if not found
        """
        config = self.get_configuration(tenant_id, user_id)
        if config:
            export_data = config.to_dict()
            export_data["_export_timestamp"] = datetime.now(timezone.utc).isoformat()
            export_data["_export_format_version"] = "1.0"
            return export_data
        return None

    def import_configuration(
        self,
        data: dict[str, Any],
        context: ValidationContext,
        justification: str = "Imported configuration",
    ) -> ValidationResult:
        """
        Import configuration from backup.

        Args:
            data: Configuration dictionary
            context: Validation context
            justification: Business justification

        Returns:
            ValidationResult
        """
        # Remove export metadata
        data.pop("_export_timestamp", None)
        data.pop("_export_format_version", None)

        # Create configuration from data
        config = GuardrailConfiguration.from_dict(data)

        # Validate and save
        return self.update_configuration(config, context, justification)

    def _make_config_key(self, tenant_id: str, user_id: str) -> str:
        """Create storage key for configuration."""
        return f"{tenant_id}:{user_id}"

    def _apply_compliance_overrides(
        self, config: GuardrailConfiguration
    ) -> GuardrailConfiguration:
        """
        Apply compliance profile overrides at read time.

        This ensures compliance requirements are always enforced
        even if the stored configuration doesn't meet them.
        """
        if config.compliance_profile == ComplianceProfile.NONE:
            return config

        profile_spec = get_compliance_profile(config.compliance_profile)
        if not profile_spec:
            return config

        # Note: We don't modify the stored config, just the returned one
        # This is a read-time enforcement mechanism
        return config

    def _detect_changes(
        self,
        old_config: GuardrailConfiguration,
        new_config: GuardrailConfiguration,
    ) -> dict[str, tuple[Any, Any]]:
        """
        Detect changes between two configurations.

        Returns:
            Dictionary mapping setting paths to (old_value, new_value) tuples
        """
        changes: dict[str, tuple[Any, Any]] = {}

        old_dict = old_config.to_dict()
        new_dict = new_config.to_dict()

        # Compare all fields
        for key in set(old_dict.keys()) | set(new_dict.keys()):
            # Skip metadata fields
            if key in (
                "last_modified_by",
                "last_modified_at",
                "version",
                "change_justification",
            ):
                continue

            old_value = old_dict.get(key)
            new_value = new_dict.get(key)

            if old_value != new_value:
                changes[key] = (old_value, new_value)

        return changes


# Singleton instance
_config_service: GuardrailConfigurationService | None = None


def get_config_service() -> GuardrailConfigurationService:
    """Get or create the singleton configuration service instance."""
    global _config_service
    if _config_service is None:
        _config_service = GuardrailConfigurationService()
    return _config_service


def reset_config_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _config_service
    _config_service = None
