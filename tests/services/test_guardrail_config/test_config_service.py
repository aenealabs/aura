"""
Tests for guardrail configuration service (ADR-069).
"""

from src.services.guardrail_config import (
    ComplianceProfile,
    GuardrailConfiguration,
    HITLSensitivity,
    SecurityProfile,
    TrustLevel,
    ValidationContext,
    Verbosity,
    get_config_service,
)


class TestConfigurationCRUD:
    """Tests for configuration CRUD operations."""

    def test_get_configuration_not_found(self, config_service):
        """Test getting non-existent configuration returns None."""
        result = config_service.get_configuration("unknown-tenant", "unknown-user")
        assert result is None

    def test_get_or_create_configuration_creates_default(self, config_service):
        """Test get_or_create creates default configuration."""
        config = config_service.get_or_create_configuration("new-tenant", "new-user")
        assert config is not None
        assert config.tenant_id == "new-tenant"
        assert config.user_id == "new-user"
        assert config.security_profile == SecurityProfile.BALANCED

    def test_get_or_create_configuration_returns_existing(
        self, config_service, admin_context
    ):
        """Test get_or_create returns existing configuration."""
        # Create a configuration first
        config1 = config_service.get_or_create_configuration("test-tenant", "test-user")

        # Modify it
        config1.security_profile = SecurityProfile.CONSERVATIVE
        config_service.update_configuration(
            config1, admin_context, "Changed to conservative"
        )

        # Get it again
        config2 = config_service.get_or_create_configuration("test-tenant", "test-user")
        assert config2.security_profile == SecurityProfile.CONSERVATIVE

    def test_update_configuration_success(
        self, config_service, balanced_config, admin_context
    ):
        """Test successful configuration update."""
        # Create initial config
        config_service._configurations["test-tenant:test-user"] = balanced_config

        # Update it
        new_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            security_profile=SecurityProfile.CONSERVATIVE,
            audit_retention_days=730,
        )
        result = config_service.update_configuration(
            new_config, admin_context, "Hardening security"
        )

        assert result.valid is True
        assert result.effective_config is not None
        assert result.effective_config.security_profile == SecurityProfile.CONSERVATIVE

    def test_update_configuration_increments_version(
        self, config_service, balanced_config, admin_context
    ):
        """Test update increments version."""
        # Create initial config
        balanced_config.version = 1
        config_service._configurations["test-tenant:test-user"] = balanced_config

        # Update it
        new_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            security_profile=SecurityProfile.CONSERVATIVE,
        )
        result = config_service.update_configuration(new_config, admin_context, "Test")

        assert result.valid is True
        saved_config = config_service.get_configuration("test-tenant", "test-user")
        assert saved_config.version == 2

    def test_update_configuration_records_change(
        self, config_service, balanced_config, admin_context
    ):
        """Test update records change in history."""
        # Create initial config
        config_service._configurations["test-tenant:test-user"] = balanced_config

        # Update it
        new_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            security_profile=SecurityProfile.CONSERVATIVE,
        )
        config_service.update_configuration(
            new_config, admin_context, "Test justification"
        )

        # Check change history
        history = config_service.get_change_history("test-tenant")
        assert len(history) > 0
        assert any(r.setting_path == "security_profile" for r in history)
        assert any(r.justification == "Test justification" for r in history)

    def test_update_configuration_validation_failure(
        self, config_service, admin_context
    ):
        """Test update fails with invalid configuration."""
        invalid_config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            audit_retention_days=30,  # Below minimum
        )
        result = config_service.update_configuration(
            invalid_config, admin_context, "Test"
        )

        assert result.valid is False
        assert len(result.errors) > 0

    def test_delete_configuration_success(
        self, config_service, balanced_config, admin_context
    ):
        """Test successful configuration deletion."""
        # Create config
        config_service._configurations["test-tenant:test-user"] = balanced_config

        # Delete it
        result = config_service.delete_configuration(
            "test-tenant", "test-user", admin_context, "No longer needed"
        )

        assert result is True
        assert config_service.get_configuration("test-tenant", "test-user") is None

    def test_delete_configuration_not_found(self, config_service, admin_context):
        """Test delete returns False for non-existent config."""
        result = config_service.delete_configuration(
            "unknown-tenant", "unknown-user", admin_context, "Test"
        )
        assert result is False

    def test_delete_configuration_records_change(
        self, config_service, balanced_config, admin_context
    ):
        """Test delete records change in history."""
        # Create config
        config_service._configurations["test-tenant:test-user"] = balanced_config

        # Delete it
        config_service.delete_configuration(
            "test-tenant", "test-user", admin_context, "No longer needed"
        )

        # Check change history
        history = config_service.get_change_history("test-tenant")
        assert len(history) > 0
        assert any(r.change_type == "delete" for r in history)


class TestResetToDefaults:
    """Tests for reset to defaults functionality."""

    def test_reset_to_defaults(
        self, config_service, conservative_config, admin_context
    ):
        """Test reset to defaults restores default values."""
        # Create custom config
        config_service._configurations["test-tenant:test-user"] = conservative_config

        # Reset to defaults
        result = config_service.reset_to_defaults(
            "test-tenant", "test-user", admin_context, "Starting fresh"
        )

        assert result.valid is True
        saved_config = config_service.get_configuration("test-tenant", "test-user")
        assert saved_config.security_profile == SecurityProfile.BALANCED
        assert saved_config.hitl_sensitivity == HITLSensitivity.MEDIUM

    def test_reset_to_defaults_increments_version(
        self, config_service, balanced_config, admin_context
    ):
        """Test reset increments version."""
        balanced_config.version = 5
        config_service._configurations["test-tenant:test-user"] = balanced_config

        result = config_service.reset_to_defaults(
            "test-tenant", "test-user", admin_context
        )

        assert result.valid is True
        saved_config = config_service.get_configuration("test-tenant", "test-user")
        assert saved_config.version == 6

    def test_reset_to_defaults_records_change(
        self, config_service, balanced_config, admin_context
    ):
        """Test reset records change in history."""
        config_service._configurations["test-tenant:test-user"] = balanced_config

        config_service.reset_to_defaults("test-tenant", "test-user", admin_context)

        history = config_service.get_change_history("test-tenant")
        assert len(history) > 0
        assert any(r.change_type == "reset" for r in history)


class TestChangeHistory:
    """Tests for change history functionality."""

    def test_get_change_history_empty(self, config_service):
        """Test empty change history."""
        history = config_service.get_change_history("test-tenant")
        assert history == []

    def test_get_change_history_filtered_by_tenant(
        self, config_service, balanced_config, admin_context
    ):
        """Test change history filtered by tenant."""
        # Create changes for different tenants
        config1 = GuardrailConfiguration(tenant_id="tenant-1", user_id="user-1")
        config2 = GuardrailConfiguration(tenant_id="tenant-2", user_id="user-2")

        context1 = ValidationContext(
            user_id="user-1", tenant_id="tenant-1", is_admin=True
        )
        context2 = ValidationContext(
            user_id="user-2", tenant_id="tenant-2", is_admin=True
        )

        config_service.update_configuration(config1, context1, "Test 1")
        config_service.update_configuration(config2, context2, "Test 2")

        # Get history for tenant-1 only
        history = config_service.get_change_history("tenant-1")
        assert all(r.tenant_id == "tenant-1" for r in history)

    def test_get_change_history_filtered_by_user(self, config_service, admin_context):
        """Test change history filtered by user."""
        # Create changes for different users
        config1 = GuardrailConfiguration(tenant_id="test-tenant", user_id="user-1")
        config2 = GuardrailConfiguration(tenant_id="test-tenant", user_id="user-2")

        context1 = ValidationContext(
            user_id="user-1", tenant_id="test-tenant", is_admin=True
        )
        context2 = ValidationContext(
            user_id="user-2", tenant_id="test-tenant", is_admin=True
        )

        config_service.update_configuration(config1, context1, "Test 1")
        config_service.update_configuration(config2, context2, "Test 2")

        # Get history for user-1 only
        history = config_service.get_change_history("test-tenant", user_id="user-1")
        assert all(r.user_id == "user-1" for r in history)

    def test_get_change_history_limited(self, config_service, admin_context):
        """Test change history respects limit."""
        # Create multiple changes
        for i in range(10):
            config = GuardrailConfiguration(
                tenant_id="test-tenant",
                user_id="test-user",
                audit_retention_days=100 + i,
            )
            config_service.update_configuration(config, admin_context, f"Change {i}")

        # Get limited history
        history = config_service.get_change_history("test-tenant", limit=5)
        assert len(history) <= 5

    def test_get_change_history_sorted_by_timestamp(
        self, config_service, admin_context
    ):
        """Test change history sorted by timestamp descending."""
        # Create multiple changes
        for i in range(5):
            config = GuardrailConfiguration(
                tenant_id="test-tenant",
                user_id="test-user",
                audit_retention_days=100 + i,
            )
            config_service.update_configuration(config, admin_context, f"Change {i}")

        history = config_service.get_change_history("test-tenant")
        for i in range(len(history) - 1):
            assert history[i].timestamp >= history[i + 1].timestamp


class TestComplianceProfileApplication:
    """Tests for compliance profile application."""

    def test_apply_soc2_profile(self, config_service, balanced_config, admin_context):
        """Test applying SOC2 compliance profile."""
        config_service._configurations["test-tenant:test-user"] = balanced_config

        result = config_service.apply_compliance_profile(
            "test-tenant",
            "test-user",
            ComplianceProfile.SOC2,
            admin_context,
            "Compliance requirement",
        )

        assert result.valid is True
        saved_config = config_service.get_configuration("test-tenant", "test-user")
        assert saved_config.compliance_profile == ComplianceProfile.SOC2
        assert saved_config.audit_retention_days >= 365

    def test_apply_fedramp_high_profile_upgrades_settings(
        self, config_service, admin_context
    ):
        """Test FedRAMP High upgrades settings to meet requirements."""
        # Create config with low settings
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            audit_retention_days=365,
            min_context_trust=TrustLevel.LOW,
            explanation_verbosity=Verbosity.MINIMAL,
        )
        config_service._configurations["test-tenant:test-user"] = config

        result = config_service.apply_compliance_profile(
            "test-tenant",
            "test-user",
            ComplianceProfile.FEDRAMP_HIGH,
            admin_context,
        )

        assert result.valid is True
        saved_config = config_service.get_configuration("test-tenant", "test-user")
        assert saved_config.audit_retention_days >= 2555  # 7 years
        assert saved_config.min_context_trust == TrustLevel.HIGH
        assert saved_config.explanation_verbosity == Verbosity.DETAILED

    def test_apply_cmmc_l2_upgrades_trust_level(self, config_service, admin_context):
        """Test CMMC L2 upgrades trust level to MEDIUM."""
        config = GuardrailConfiguration(
            tenant_id="test-tenant",
            user_id="test-user",
            min_context_trust=TrustLevel.ALL,
        )
        config_service._configurations["test-tenant:test-user"] = config

        result = config_service.apply_compliance_profile(
            "test-tenant",
            "test-user",
            ComplianceProfile.CMMC_L2,
            admin_context,
        )

        assert result.valid is True
        saved_config = config_service.get_configuration("test-tenant", "test-user")
        assert saved_config.min_context_trust == TrustLevel.MEDIUM


class TestExportImport:
    """Tests for configuration export/import."""

    def test_export_configuration(self, config_service, balanced_config):
        """Test configuration export."""
        config_service._configurations["test-tenant:test-user"] = balanced_config

        export_data = config_service.export_configuration("test-tenant", "test-user")

        assert export_data is not None
        assert export_data["tenant_id"] == "test-tenant"
        assert export_data["security_profile"] == "balanced"
        assert "_export_timestamp" in export_data
        assert "_export_format_version" in export_data

    def test_export_configuration_not_found(self, config_service):
        """Test export returns None for non-existent config."""
        result = config_service.export_configuration("unknown", "unknown")
        assert result is None

    def test_import_configuration(self, config_service, admin_context):
        """Test configuration import."""
        export_data = {
            "tenant_id": "imported-tenant",
            "user_id": "imported-user",
            "security_profile": "conservative",
            "hitl_sensitivity": "low",
            "min_context_trust": "high",
            "explanation_verbosity": "detailed",
            "quarantine_reviewer": "security_team",
            "audit_retention_days": 730,
            "compliance_profile": "none",
            "_export_timestamp": "2024-01-01T00:00:00+00:00",
            "_export_format_version": "1.0",
        }

        context = ValidationContext(
            user_id="imported-user",
            tenant_id="imported-tenant",
            is_admin=True,
        )

        result = config_service.import_configuration(
            export_data, context, "Restored from backup"
        )

        assert result.valid is True
        saved_config = config_service.get_configuration(
            "imported-tenant", "imported-user"
        )
        assert saved_config.security_profile == SecurityProfile.CONSERVATIVE
        assert saved_config.audit_retention_days == 730

    def test_import_configuration_validates(self, config_service, admin_context):
        """Test import validates the configuration."""
        invalid_export = {
            "tenant_id": "test-tenant",
            "user_id": "test-user",
            "security_profile": "balanced",
            "hitl_sensitivity": "medium",
            "min_context_trust": "medium",
            "explanation_verbosity": "standard",
            "quarantine_reviewer": "team_lead",
            "audit_retention_days": 30,  # Invalid - below minimum
            "compliance_profile": "none",
        }

        result = config_service.import_configuration(
            invalid_export, admin_context, "Test"
        )

        assert result.valid is False


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_config_service_returns_same_instance(self):
        """Test singleton returns same instance."""
        service1 = get_config_service()
        service2 = get_config_service()
        assert service1 is service2
