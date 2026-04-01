"""
Tests for Autonomy Policy Service

Tests the configurable HITL toggle and autonomy policy management
that enables Aura to operate at 85% autonomy for commercial enterprises.
"""

import pytest

from src.services.autonomy_policy_service import (
    AutonomyLevel,
    AutonomyPolicy,
    AutonomyServiceMode,
    create_autonomy_policy_service,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_service():
    """Create a mock autonomy policy service."""
    return create_autonomy_policy_service(mode=AutonomyServiceMode.MOCK)


@pytest.fixture
def defense_policy(mock_service):
    """Create a defense contractor policy."""
    return mock_service.create_policy_from_preset(
        organization_id="defense-org",
        preset_name="defense_contractor",
        created_by="admin@defense.gov",
    )


@pytest.fixture
def autonomous_policy(mock_service):
    """Create a fully autonomous policy."""
    policy = mock_service.create_policy_from_preset(
        organization_id="dev-org",
        preset_name="fully_autonomous",
        created_by="admin@dev.io",
    )
    # The preset might not set hitl_enabled=False by default in create_policy_from_preset
    # so we explicitly toggle it off for test consistency
    mock_service.toggle_hitl(policy.policy_id, hitl_enabled=False)
    return mock_service.get_policy(policy.policy_id)


@pytest.fixture
def enterprise_policy(mock_service):
    """Create an enterprise standard policy."""
    return mock_service.create_policy_from_preset(
        organization_id="enterprise-org",
        preset_name="enterprise_standard",
        created_by="admin@enterprise.com",
    )


# ============================================================================
# AutonomyPolicy Tests
# ============================================================================


class TestAutonomyPolicy:
    """Tests for AutonomyPolicy dataclass."""

    def test_from_preset_defense_contractor(self):
        """Test defense contractor preset creates correct policy."""
        policy = AutonomyPolicy.from_preset("defense_contractor", "org-1")

        assert policy.organization_id == "org-1"
        assert policy.default_level == AutonomyLevel.FULL_HITL
        assert policy.hitl_enabled is True
        assert policy.preset_name == "defense_contractor"
        assert "production_deployment" in policy.guardrails

    def test_from_preset_fully_autonomous(self):
        """Test fully autonomous preset disables HITL."""
        policy = AutonomyPolicy.from_preset("fully_autonomous", "org-1")

        assert policy.hitl_enabled is False
        assert policy.default_level == AutonomyLevel.FULL_AUTONOMOUS
        # Guardrails should still be present
        assert len(policy.guardrails) > 0

    def test_from_preset_unknown_raises(self):
        """Test unknown preset raises ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            AutonomyPolicy.from_preset("nonexistent_preset", "org-1")

    def test_get_autonomy_level_guardrail_override(self):
        """Test guardrails always return FULL_HITL."""
        policy = AutonomyPolicy.from_preset("fully_autonomous", "org-1")

        # Even with fully autonomous default, guardrails override
        level = policy.get_autonomy_level(
            severity="LOW",
            operation="production_deployment",  # Guardrail
            repository="any-repo",
        )
        assert level == AutonomyLevel.FULL_HITL

    def test_get_autonomy_level_severity_override(self):
        """Test severity overrides work correctly."""
        policy = AutonomyPolicy.from_preset("enterprise_standard", "org-1")

        # LOW severity should be FULL_AUTONOMOUS
        level = policy.get_autonomy_level(
            severity="LOW",
            operation="security_patch",
            repository="repo",
        )
        assert level == AutonomyLevel.FULL_AUTONOMOUS

        # CRITICAL should use default (CRITICAL_HITL)
        level = policy.get_autonomy_level(
            severity="CRITICAL",
            operation="security_patch",
            repository="repo",
        )
        assert level == AutonomyLevel.CRITICAL_HITL

    def test_requires_hitl_when_disabled(self):
        """Test HITL requirements when disabled."""
        policy = AutonomyPolicy.from_preset("fully_autonomous", "org-1")
        assert policy.hitl_enabled is False

        # Normal operations should not require HITL
        requires = policy.requires_hitl(
            severity="CRITICAL",
            operation="security_patch",
            repository="repo",
        )
        assert requires is False

        # Guardrails should STILL require HITL
        requires = policy.requires_hitl(
            severity="LOW",
            operation="production_deployment",
            repository="repo",
        )
        assert requires is True

    def test_requires_hitl_critical_hitl_mode(self):
        """Test CRITICAL_HITL only requires HITL for HIGH/CRITICAL."""
        policy = AutonomyPolicy.from_preset("enterprise_standard", "org-1")

        # HIGH should require HITL
        assert policy.requires_hitl("HIGH", "security_patch", "") is True

        # CRITICAL should require HITL
        assert policy.requires_hitl("CRITICAL", "security_patch", "") is True

        # MEDIUM should NOT require HITL (override to AUDIT_ONLY)
        assert policy.requires_hitl("MEDIUM", "security_patch", "") is False

        # LOW should NOT require HITL (override to FULL_AUTONOMOUS)
        assert policy.requires_hitl("LOW", "security_patch", "") is False

    def test_to_dict_and_from_dict(self):
        """Test serialization round-trip."""
        original = AutonomyPolicy.from_preset("fintech_startup", "org-1")

        # Serialize
        data = original.to_dict()
        assert isinstance(data, dict)
        assert data["organization_id"] == "org-1"
        assert data["default_level"] == "critical_hitl"

        # Deserialize
        restored = AutonomyPolicy.from_dict(data)
        assert restored.organization_id == original.organization_id
        assert restored.default_level == original.default_level
        assert restored.hitl_enabled == original.hitl_enabled


# ============================================================================
# AutonomyPolicyService Tests
# ============================================================================


class TestAutonomyPolicyService:
    """Tests for AutonomyPolicyService."""

    def test_create_policy_from_preset(self, mock_service):
        """Test creating policy from preset."""
        policy = mock_service.create_policy_from_preset(
            organization_id="test-org",
            preset_name="fintech_startup",
            created_by="admin",
        )

        assert policy.policy_id.startswith("policy-")
        assert policy.organization_id == "test-org"
        assert policy.preset_name == "fintech_startup"
        assert policy.created_by == "admin"

    def test_create_policy_custom(self, mock_service):
        """Test creating custom policy."""
        policy = mock_service.create_policy(
            organization_id="custom-org",
            name="Custom Policy",
            description="My custom policy",
            hitl_enabled=True,
            default_level=AutonomyLevel.AUDIT_ONLY,
            created_by="admin",
        )

        assert policy.name == "Custom Policy"
        assert policy.description == "My custom policy"
        assert policy.default_level == AutonomyLevel.AUDIT_ONLY

    def test_get_policy(self, mock_service, defense_policy):
        """Test retrieving policy by ID."""
        retrieved = mock_service.get_policy(defense_policy.policy_id)

        assert retrieved is not None
        assert retrieved.policy_id == defense_policy.policy_id
        assert retrieved.organization_id == defense_policy.organization_id

    def test_get_policy_not_found(self, mock_service):
        """Test retrieving non-existent policy."""
        result = mock_service.get_policy("nonexistent-policy-id")
        assert result is None

    def test_get_policy_for_organization(self, mock_service, defense_policy):
        """Test retrieving policy by organization."""
        retrieved = mock_service.get_policy_for_organization("defense-org")

        assert retrieved is not None
        assert retrieved.organization_id == "defense-org"

    def test_update_policy(self, mock_service, defense_policy):
        """Test updating policy."""
        updated = mock_service.update_policy(
            policy_id=defense_policy.policy_id,
            updates={
                "name": "Updated Name",
                "description": "Updated description",
            },
            updated_by="admin",
        )

        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"
        assert updated.updated_by == "admin"

    def test_toggle_hitl_off(self, mock_service, defense_policy):
        """Test disabling HITL."""
        assert defense_policy.hitl_enabled is True

        updated = mock_service.toggle_hitl(
            policy_id=defense_policy.policy_id,
            hitl_enabled=False,
            updated_by="admin",
            reason="Enabling autonomous mode for dev",
        )

        assert updated is not None
        assert updated.hitl_enabled is False

    def test_toggle_hitl_on(self, mock_service, autonomous_policy):
        """Test enabling HITL."""
        assert autonomous_policy.hitl_enabled is False

        updated = mock_service.toggle_hitl(
            policy_id=autonomous_policy.policy_id,
            hitl_enabled=True,
            updated_by="admin",
            reason="Re-enabling HITL for compliance",
        )

        assert updated is not None
        assert updated.hitl_enabled is True

    def test_add_severity_override(self, mock_service, defense_policy):
        """Test adding severity override."""
        updated = mock_service.add_override(
            policy_id=defense_policy.policy_id,
            override_type="severity",
            context_value="LOW",
            autonomy_level=AutonomyLevel.FULL_AUTONOMOUS,
            updated_by="admin",
        )

        assert updated is not None
        assert "LOW" in updated.severity_overrides
        assert updated.severity_overrides["LOW"] == AutonomyLevel.FULL_AUTONOMOUS

    def test_add_operation_override(self, mock_service, enterprise_policy):
        """Test adding operation override."""
        updated = mock_service.add_override(
            policy_id=enterprise_policy.policy_id,
            override_type="operation",
            context_value="documentation_update",
            autonomy_level=AutonomyLevel.FULL_AUTONOMOUS,
            updated_by="admin",
        )

        assert updated is not None
        assert "documentation_update" in updated.operation_overrides

    def test_add_repository_override(self, mock_service, enterprise_policy):
        """Test adding repository override."""
        updated = mock_service.add_override(
            policy_id=enterprise_policy.policy_id,
            override_type="repository",
            context_value="internal/tooling",
            autonomy_level=AutonomyLevel.FULL_AUTONOMOUS,
            updated_by="admin",
        )

        assert updated is not None
        assert "internal/tooling" in updated.repository_overrides

    def test_remove_override(self, mock_service, defense_policy):
        """Test removing override."""
        # First add an override
        mock_service.add_override(
            policy_id=defense_policy.policy_id,
            override_type="severity",
            context_value="LOW",
            autonomy_level=AutonomyLevel.AUDIT_ONLY,
            updated_by="admin",
        )

        # Then remove it
        updated = mock_service.remove_override(
            policy_id=defense_policy.policy_id,
            override_type="severity",
            context_value="LOW",
            updated_by="admin",
        )

        assert updated is not None
        assert "LOW" not in updated.severity_overrides

    def test_delete_policy(self, mock_service, defense_policy):
        """Test deleting (deactivating) policy."""
        success = mock_service.delete_policy(
            policy_id=defense_policy.policy_id,
            deleted_by="admin",
            reason="Policy no longer needed",
        )

        assert success is True

        # Policy should be inactive
        policy = mock_service.get_policy(defense_policy.policy_id)
        assert policy.is_active is False

    def test_requires_hitl_approval(self, mock_service, defense_policy):
        """Test HITL requirement check."""
        # Defense policy with FULL_HITL default requires HITL for HIGH/CRITICAL
        # but LOW severity has CRITICAL_HITL override (only HIGH/CRITICAL require HITL)
        requires = mock_service.requires_hitl_approval(
            policy_id=defense_policy.policy_id,
            severity="CRITICAL",
            operation="security_patch",
        )
        assert requires is True

        # LOW severity uses CRITICAL_HITL override, so doesn't require HITL
        requires_low = mock_service.requires_hitl_approval(
            policy_id=defense_policy.policy_id,
            severity="LOW",
            operation="security_patch",
        )
        assert requires_low is False

    def test_requires_hitl_approval_not_found(self, mock_service):
        """Test HITL check defaults to True for missing policy."""
        requires = mock_service.requires_hitl_approval(
            policy_id="nonexistent",
            severity="LOW",
            operation="security_patch",
        )
        assert requires is True  # Default to safe behavior

    def test_list_policies(self, mock_service, defense_policy, enterprise_policy):
        """Test listing policies for organization."""
        policies = mock_service.list_policies(
            organization_id="defense-org",
        )

        assert len(policies) == 1
        assert policies[0].organization_id == "defense-org"

    def test_list_policies_all(self, mock_service, defense_policy, enterprise_policy):
        """Test listing all policies."""
        policies = mock_service.list_policies()

        assert len(policies) >= 2

    def test_get_available_presets(self, mock_service):
        """Test getting available presets."""
        presets = mock_service.get_available_presets()

        assert len(presets) == 7
        names = [p["name"] for p in presets]
        assert "defense_contractor" in names
        assert "fully_autonomous" in names
        assert "enterprise_standard" in names

    def test_record_autonomous_decision(self, mock_service, enterprise_policy):
        """Test recording autonomous decision."""
        decision = mock_service.record_autonomous_decision(
            policy_id=enterprise_policy.policy_id,
            execution_id="exec-123",
            severity="LOW",
            operation="security_patch",
            repository="test/repo",
            autonomy_level=AutonomyLevel.FULL_AUTONOMOUS,
            hitl_required=False,
            hitl_bypassed=False,
            auto_approved=True,
        )

        assert decision.decision_id.startswith("decision-")
        assert decision.execution_id == "exec-123"
        assert decision.auto_approved is True

    def test_audit_log_created(self, mock_service, defense_policy):
        """Test audit log entries are created."""
        # Toggle HITL to create audit entry
        mock_service.toggle_hitl(
            policy_id=defense_policy.policy_id,
            hitl_enabled=False,
            updated_by="admin",
        )

        audit = mock_service.get_audit_log(policy_id=defense_policy.policy_id)

        # Should have at least 2 entries: creation + toggle
        assert len(audit) >= 2


# ============================================================================
# Integration Tests - Autonomy Scenarios
# ============================================================================


class TestAutonomyScenarios:
    """Integration tests for real-world autonomy scenarios."""

    def test_defense_contractor_hitl_requirements(self, mock_service, defense_policy):
        """Defense contractors require HITL for HIGH/CRITICAL operations.

        The defense_contractor preset has:
        - default_level: FULL_HITL (requires HITL for all severities)
        - severity_overrides: LOW -> CRITICAL_HITL (only HIGH/CRITICAL require HITL)

        This allows some automation for low-risk activities even in regulated environments.
        """
        test_cases = [
            ("CRITICAL", "security_patch", True),  # FULL_HITL default
            ("HIGH", "security_patch", True),  # FULL_HITL default
            ("MEDIUM", "security_patch", True),  # FULL_HITL default
            ("LOW", "security_patch", False),  # CRITICAL_HITL override
            ("LOW", "documentation_update", False),  # CRITICAL_HITL override
        ]

        for severity, operation, expected in test_cases:
            requires = mock_service.requires_hitl_approval(
                policy_id=defense_policy.policy_id,
                severity=severity,
                operation=operation,
            )
            assert requires == expected, f"Failed for {severity}/{operation}"

    def test_enterprise_standard_gradual_autonomy(
        self, mock_service, enterprise_policy
    ):
        """Enterprise standard allows gradual autonomy based on severity."""
        test_cases = [
            ("CRITICAL", "security_patch", True),  # HITL required
            ("HIGH", "security_patch", True),  # HITL required
            ("MEDIUM", "security_patch", False),  # AUDIT_ONLY
            ("LOW", "security_patch", False),  # FULL_AUTONOMOUS
        ]

        for severity, operation, expected in test_cases:
            requires = mock_service.requires_hitl_approval(
                policy_id=enterprise_policy.policy_id,
                severity=severity,
                operation=operation,
            )
            assert requires == expected, f"Failed for {severity}/{operation}"

    def test_fully_autonomous_guardrails_still_apply(
        self, mock_service, autonomous_policy
    ):
        """Even fully autonomous policies respect guardrails."""
        # Regular operations should not require HITL
        requires = mock_service.requires_hitl_approval(
            policy_id=autonomous_policy.policy_id,
            severity="CRITICAL",
            operation="security_patch",
        )
        assert requires is False

        # Guardrails should ALWAYS require HITL
        guardrail_operations = [
            "production_deployment",
            "credential_modification",
            "access_control_change",
            "database_migration",
            "infrastructure_change",
        ]

        for operation in guardrail_operations:
            requires = mock_service.requires_hitl_approval(
                policy_id=autonomous_policy.policy_id,
                severity="LOW",
                operation=operation,
            )
            assert requires is True, f"Guardrail not enforced for {operation}"

    def test_policy_transition_defense_to_autonomous(self, mock_service):
        """Test transitioning from defense to autonomous as organization matures."""
        # Start with defense preset
        policy = mock_service.create_policy_from_preset(
            organization_id="transitioning-org",
            preset_name="defense_contractor",
            created_by="admin",
        )

        # Initial state: defense_contractor already has LOW->CRITICAL_HITL override
        # so LOW severity doesn't require HITL, but MEDIUM/HIGH/CRITICAL do
        assert (
            mock_service.requires_hitl_approval(
                policy_id=policy.policy_id,
                severity="MEDIUM",
                operation="security_patch",
            )
            is True
        )

        assert (
            mock_service.requires_hitl_approval(
                policy_id=policy.policy_id,
                severity="LOW",
                operation="security_patch",
            )
            is False
        )  # Already CRITICAL_HITL for LOW

        # Phase 1: Allow MEDIUM severity to be autonomous too
        mock_service.add_override(
            policy_id=policy.policy_id,
            override_type="severity",
            context_value="MEDIUM",
            autonomy_level=AutonomyLevel.AUDIT_ONLY,
            updated_by="admin",
        )

        assert (
            mock_service.requires_hitl_approval(
                policy_id=policy.policy_id,
                severity="MEDIUM",
                operation="security_patch",
            )
            is False
        )

        # Phase 2: Toggle HITL off entirely
        mock_service.toggle_hitl(
            policy_id=policy.policy_id,
            hitl_enabled=False,
            updated_by="admin",
        )

        # Now even CRITICAL doesn't require HITL
        assert (
            mock_service.requires_hitl_approval(
                policy_id=policy.policy_id,
                severity="CRITICAL",
                operation="security_patch",
            )
            is False
        )

        # But guardrails STILL apply
        assert (
            mock_service.requires_hitl_approval(
                policy_id=policy.policy_id,
                severity="LOW",
                operation="production_deployment",
            )
            is True
        )


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_override_type(self, mock_service, enterprise_policy):
        """Test adding override with invalid type raises error."""
        with pytest.raises(ValueError, match="Invalid override type"):
            mock_service.add_override(
                policy_id=enterprise_policy.policy_id,
                override_type="invalid_type",
                context_value="test",
                autonomy_level=AutonomyLevel.FULL_HITL,
            )

    def test_update_nonexistent_policy(self, mock_service):
        """Test updating non-existent policy returns None."""
        result = mock_service.update_policy(
            policy_id="nonexistent",
            updates={"name": "New Name"},
        )
        assert result is None

    def test_delete_nonexistent_policy(self, mock_service):
        """Test deleting non-existent policy returns False."""
        result = mock_service.delete_policy("nonexistent")
        assert result is False

    def test_case_insensitive_severity(self, mock_service, enterprise_policy):
        """Test severity checks are case-insensitive."""
        # Test with different cases
        for severity in ["low", "LOW", "Low"]:
            requires = mock_service.requires_hitl_approval(
                policy_id=enterprise_policy.policy_id,
                severity=severity,
                operation="security_patch",
            )
            # LOW should not require HITL for enterprise_standard
            assert requires is False, f"Case sensitivity issue with {severity}"

    def test_policy_cache(self, mock_service, defense_policy):
        """Test policy caching works correctly."""
        # First retrieval
        policy1 = mock_service.get_policy(defense_policy.policy_id)

        # Second retrieval (should hit cache)
        policy2 = mock_service.get_policy(defense_policy.policy_id)

        # Should be same object from cache
        assert policy1 is policy2

        # Update should invalidate cache
        mock_service.update_policy(
            policy_id=defense_policy.policy_id,
            updates={"name": "Updated"},
        )

        # Next retrieval should get fresh data
        policy3 = mock_service.get_policy(defense_policy.policy_id)
        assert policy3.name == "Updated"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
