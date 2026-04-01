"""Tests for Environment Validator Remediation Strategies (ADR-062 Phase 4)."""

import pytest

from src.services.env_validator.models import Severity, Violation
from src.services.env_validator.remediation_engine import RemediationRisk
from src.services.env_validator.remediation_strategies import (
    ConfigMapValueStrategy,
    EnvironmentVariableStrategy,
    HITLOnlyStrategy,
    MockRemediationStrategy,
    ResourceNamingStrategy,
    TagConsistencyStrategy,
    get_default_strategies,
)


# Test fixtures
@pytest.fixture
def env_var_violation():
    """ENV-101 violation for ENVIRONMENT variable."""
    return Violation(
        rule_id="ENV-101",
        severity=Severity.WARNING,
        resource_type="ConfigMap",
        resource_name="aura-api-config",
        field_path="data.ENVIRONMENT",
        expected_value="qa",
        actual_value="dev",
        message="ENVIRONMENT variable mismatch",
        suggested_fix="Set ENVIRONMENT=qa",
        auto_remediable=True,
    )


@pytest.fixture
def naming_violation():
    """ENV-201 violation for resource naming."""
    return Violation(
        rule_id="ENV-201",
        severity=Severity.INFO,
        resource_type="ConfigMap",
        resource_name="test-config",
        field_path="metadata.name",
        expected_value="aura-test-config",
        actual_value="test-config",
        message="Resource naming convention violation",
        auto_remediable=True,
    )


@pytest.fixture
def tag_violation():
    """ENV-202 violation for tag consistency."""
    return Violation(
        rule_id="ENV-202",
        severity=Severity.INFO,
        resource_type="Deployment",
        resource_name="aura-api",
        field_path="metadata.labels.environment",
        expected_value="qa",
        actual_value="",
        message="Missing environment tag",
        auto_remediable=True,
    )


@pytest.fixture
def account_violation():
    """ENV-001 violation for account ID."""
    return Violation(
        rule_id="ENV-001",
        severity=Severity.CRITICAL,
        resource_type="ConfigMap",
        resource_name="aura-api-config",
        field_path="data.TABLE_ARN",
        expected_value="arn:aws:dynamodb:us-east-1:234567890123:table/aura-tasks-qa",
        actual_value="arn:aws:dynamodb:us-east-1:123456789012:table/aura-tasks-dev",
        message="Account ID mismatch",
        auto_remediable=False,
    )


@pytest.fixture
def secret_violation():
    """ConfigMap with sensitive data (should not auto-remediate)."""
    return Violation(
        rule_id="ENV-101",
        severity=Severity.WARNING,
        resource_type="ConfigMap",
        resource_name="aura-secrets",
        field_path="data.API_KEY",
        expected_value="new-secret",
        actual_value="old-secret",
        message="Secret reference mismatch",
        auto_remediable=True,
    )


class TestEnvironmentVariableStrategy:
    """Test EnvironmentVariableStrategy."""

    def test_name(self):
        """Test strategy name."""
        strategy = EnvironmentVariableStrategy()
        assert strategy.name == "env-var-fix"

    def test_supported_rules(self):
        """Test supported rules."""
        strategy = EnvironmentVariableStrategy()
        assert "ENV-101" in strategy.supported_rules

    def test_can_remediate_configmap(self, env_var_violation):
        """Test can remediate ConfigMap violations."""
        strategy = EnvironmentVariableStrategy()
        assert strategy.can_remediate(env_var_violation, "qa") is True

    def test_can_remediate_deployment(self):
        """Test can remediate Deployment env vars."""
        strategy = EnvironmentVariableStrategy()
        violation = Violation(
            rule_id="ENV-101",
            severity=Severity.WARNING,
            resource_type="Deployment",
            resource_name="aura-api",
            field_path="spec.template.spec.containers[0].env[0].value",
            expected_value="qa",
            actual_value="dev",
            message="Environment mismatch",
            auto_remediable=True,
        )
        assert strategy.can_remediate(violation, "dev") is True

    def test_cannot_remediate_wrong_rule(self, naming_violation):
        """Test cannot remediate wrong rule type."""
        strategy = EnvironmentVariableStrategy()
        assert strategy.can_remediate(naming_violation, "qa") is False

    def test_cannot_remediate_wrong_resource(self):
        """Test cannot remediate unsupported resource types."""
        strategy = EnvironmentVariableStrategy()
        violation = Violation(
            rule_id="ENV-101",
            severity=Severity.WARNING,
            resource_type="Service",
            resource_name="aura-api-svc",
            field_path="metadata.labels.env",
            expected_value="qa",
            actual_value="dev",
            message="env label mismatch",
            auto_remediable=True,
        )
        assert strategy.can_remediate(violation, "qa") is False

    def test_risk_level_is_safe(self, env_var_violation):
        """Test risk level is always safe."""
        strategy = EnvironmentVariableStrategy()
        assert strategy.get_risk_level(env_var_violation, "dev") == RemediationRisk.SAFE
        assert (
            strategy.get_risk_level(env_var_violation, "prod") == RemediationRisk.SAFE
        )

    def test_create_patch(self, env_var_violation):
        """Test creating a patch."""
        strategy = EnvironmentVariableStrategy()
        patch, description = strategy.create_patch(env_var_violation, "qa")

        assert "patches" in patch
        assert len(patch["patches"]) == 1
        assert patch["patches"][0]["op"] == "replace"
        assert patch["patches"][0]["path"] == "/data/ENVIRONMENT"
        assert patch["patches"][0]["value"] == "qa"
        assert "aura-api-config" in description

    def test_apply_patch_dry_run(self, env_var_violation):
        """Test applying patch in dry run mode."""
        strategy = EnvironmentVariableStrategy()
        patch, _ = strategy.create_patch(env_var_violation, "qa")

        success, error = strategy.apply_patch(
            env_var_violation, patch, "qa", dry_run=True
        )

        assert success is True
        assert error is None

    def test_convert_json_pointer(self):
        """Test JSON pointer conversion."""
        strategy = EnvironmentVariableStrategy()

        # Simple path
        assert (
            strategy._convert_to_json_pointer("data.ENVIRONMENT") == "/data/ENVIRONMENT"
        )

        # Nested path
        assert (
            strategy._convert_to_json_pointer("spec.template.spec.containers")
            == "/spec/template/spec/containers"
        )

        # Path with brackets
        assert (
            strategy._convert_to_json_pointer("containers[0].env[1].value")
            == "/containers/0/env/1/value"
        )


class TestResourceNamingStrategy:
    """Test ResourceNamingStrategy."""

    def test_name(self):
        """Test strategy name."""
        strategy = ResourceNamingStrategy()
        assert strategy.name == "naming-fix"

    def test_supported_rules(self):
        """Test supported rules."""
        strategy = ResourceNamingStrategy()
        assert "ENV-201" in strategy.supported_rules

    def test_can_remediate_dev(self, naming_violation):
        """Test can remediate in dev."""
        strategy = ResourceNamingStrategy()
        assert strategy.can_remediate(naming_violation, "dev") is True

    def test_can_remediate_qa(self, naming_violation):
        """Test can remediate in qa."""
        strategy = ResourceNamingStrategy()
        assert strategy.can_remediate(naming_violation, "qa") is True

    def test_cannot_remediate_staging(self, naming_violation):
        """Test cannot auto-remediate in staging."""
        strategy = ResourceNamingStrategy()
        assert strategy.can_remediate(naming_violation, "staging") is False

    def test_cannot_remediate_prod(self, naming_violation):
        """Test cannot auto-remediate in prod."""
        strategy = ResourceNamingStrategy()
        assert strategy.can_remediate(naming_violation, "prod") is False

    def test_risk_level_dev(self, naming_violation):
        """Test risk level is low in dev."""
        strategy = ResourceNamingStrategy()
        assert strategy.get_risk_level(naming_violation, "dev") == RemediationRisk.LOW

    def test_risk_level_prod(self, naming_violation):
        """Test risk level is medium in prod."""
        strategy = ResourceNamingStrategy()
        assert (
            strategy.get_risk_level(naming_violation, "prod") == RemediationRisk.MEDIUM
        )

    def test_create_patch(self, naming_violation):
        """Test creating a naming patch."""
        strategy = ResourceNamingStrategy()
        patch, description = strategy.create_patch(naming_violation, "qa")

        assert "patches" in patch
        assert patch["patches"][0]["value"] == "aura-test-config"
        assert "naming" in description.lower()


class TestTagConsistencyStrategy:
    """Test TagConsistencyStrategy."""

    def test_name(self):
        """Test strategy name."""
        strategy = TagConsistencyStrategy()
        assert strategy.name == "tag-fix"

    def test_supported_rules(self):
        """Test supported rules."""
        strategy = TagConsistencyStrategy()
        assert "ENV-202" in strategy.supported_rules

    def test_can_remediate_dev_qa(self, tag_violation):
        """Test can remediate in dev/qa."""
        strategy = TagConsistencyStrategy()
        assert strategy.can_remediate(tag_violation, "dev") is True
        assert strategy.can_remediate(tag_violation, "qa") is True

    def test_cannot_remediate_prod(self, tag_violation):
        """Test cannot auto-remediate in prod."""
        strategy = TagConsistencyStrategy()
        assert strategy.can_remediate(tag_violation, "prod") is False

    def test_create_patch_add_tag(self, tag_violation):
        """Test creating patch to add missing tag."""
        strategy = TagConsistencyStrategy()
        patch, description = strategy.create_patch(tag_violation, "qa")

        assert patch["patches"][0]["op"] == "add"
        assert "Add" in description

    def test_create_patch_update_tag(self):
        """Test creating patch to update existing tag."""
        strategy = TagConsistencyStrategy()
        violation = Violation(
            rule_id="ENV-202",
            severity=Severity.INFO,
            resource_type="Deployment",
            resource_name="aura-api",
            field_path="metadata.labels.environment",
            expected_value="qa",
            actual_value="dev",  # Has existing value
            message="Wrong environment tag",
            auto_remediable=True,
        )

        patch, description = strategy.create_patch(violation, "qa")

        assert patch["patches"][0]["op"] == "replace"
        assert "Update" in description


class TestConfigMapValueStrategy:
    """Test ConfigMapValueStrategy."""

    def test_name(self):
        """Test strategy name."""
        strategy = ConfigMapValueStrategy()
        assert strategy.name == "configmap-value-fix"

    def test_can_remediate_non_sensitive(self, env_var_violation):
        """Test can remediate non-sensitive ConfigMap values."""
        strategy = ConfigMapValueStrategy()
        assert strategy.can_remediate(env_var_violation, "dev") is True

    def test_cannot_remediate_sensitive_field(self, secret_violation):
        """Test cannot remediate sensitive field names."""
        strategy = ConfigMapValueStrategy()
        # API_KEY in field path should be blocked
        assert strategy.can_remediate(secret_violation, "dev") is False

    def test_cannot_remediate_arn_value(self):
        """Test cannot remediate ARN values."""
        strategy = ConfigMapValueStrategy()
        violation = Violation(
            rule_id="ENV-101",
            severity=Severity.WARNING,
            resource_type="ConfigMap",
            resource_name="aura-config",
            field_path="data.TABLE_ENDPOINT",
            expected_value="qa-table",
            actual_value="arn:aws:dynamodb:us-east-1:123456789:table/dev-table",
            message="Contains ARN",
            auto_remediable=True,
        )
        assert strategy.can_remediate(violation, "dev") is False

    def test_cannot_remediate_deployment(self):
        """Test cannot remediate non-ConfigMap resources."""
        strategy = ConfigMapValueStrategy()
        violation = Violation(
            rule_id="ENV-101",
            severity=Severity.WARNING,
            resource_type="Deployment",
            resource_name="aura-api",
            field_path="spec.template.spec.containers[0].env[0].value",
            expected_value="qa",
            actual_value="dev",
            message="env mismatch",
            auto_remediable=True,
        )
        assert strategy.can_remediate(violation, "dev") is False


class TestHITLOnlyStrategy:
    """Test HITLOnlyStrategy."""

    def test_name(self):
        """Test strategy name."""
        strategy = HITLOnlyStrategy()
        assert strategy.name == "hitl-only"

    def test_supported_rules(self):
        """Test all critical rules are supported."""
        strategy = HITLOnlyStrategy()
        critical_rules = [
            "ENV-001",
            "ENV-002",
            "ENV-003",
            "ENV-004",
            "ENV-005",
            "ENV-006",
            "ENV-007",
            "ENV-008",
            "ENV-102",
            "ENV-103",
            "ENV-104",
        ]
        for rule in critical_rules:
            assert rule in strategy.supported_rules

    def test_can_remediate_critical(self, account_violation):
        """Test can create remediation for critical violations."""
        strategy = HITLOnlyStrategy()
        assert strategy.can_remediate(account_violation, "prod") is True

    def test_risk_level_is_critical(self, account_violation):
        """Test risk level is always critical."""
        strategy = HITLOnlyStrategy()
        assert (
            strategy.get_risk_level(account_violation, "dev")
            == RemediationRisk.CRITICAL
        )
        assert (
            strategy.get_risk_level(account_violation, "prod")
            == RemediationRisk.CRITICAL
        )

    def test_create_patch_includes_approval_flag(self, account_violation):
        """Test patch includes approval requirement."""
        strategy = HITLOnlyStrategy()
        patch, description = strategy.create_patch(account_violation, "qa")

        assert patch["patches"][0]["requires_approval"] is True
        assert "REQUIRES APPROVAL" in description

    def test_risk_reasons_for_all_rules(self):
        """Test risk reasons exist for all supported rules."""
        strategy = HITLOnlyStrategy()
        for rule_id in strategy.supported_rules:
            reason = strategy._get_risk_reason(rule_id)
            assert len(reason) > 10, f"Reason too short for {rule_id}: {reason}"
            # Each reason should explain why the change is impactful
            # Using broad set of keywords that cover security, operations, and data concerns
            risk_keywords = [
                "review",
                "critical",
                "security",
                "validation",
                "data",
                "routing",
                "compliance",
                "permissions",
                "identity",
                "resource",
                "deploy",
                "code",
                "access",
                "encryption",
                "integrity",
                "affects",
            ]
            has_keyword = any(kw in reason.lower() for kw in risk_keywords)
            assert (
                has_keyword
            ), f"Reason for {rule_id} missing risk explanation: {reason}"


class TestMockRemediationStrategy:
    """Test MockRemediationStrategy."""

    def test_configurable_name(self):
        """Test name is configurable."""
        strategy = MockRemediationStrategy(name="custom-mock")
        assert strategy.name == "custom-mock"

    def test_configurable_rules(self):
        """Test rules are configurable."""
        strategy = MockRemediationStrategy(rules=["CUSTOM-001", "CUSTOM-002"])
        assert "CUSTOM-001" in strategy.supported_rules
        assert "CUSTOM-002" in strategy.supported_rules

    def test_configurable_can_fix(self, env_var_violation):
        """Test can_fix is configurable."""
        strategy = MockRemediationStrategy(can_fix=False)
        assert strategy.can_remediate(env_var_violation, "qa") is False

    def test_tracks_applied_patches(self, env_var_violation):
        """Test strategy tracks applied patches."""
        strategy = MockRemediationStrategy()
        patch, _ = strategy.create_patch(env_var_violation, "qa")

        strategy.apply_patch(env_var_violation, patch, "qa", dry_run=False)

        assert len(strategy.applied_patches) == 1
        assert strategy.applied_patches[0]["violation"] == "ENV-101"

    def test_dry_run_does_not_track(self, env_var_violation):
        """Test dry run doesn't track patches."""
        strategy = MockRemediationStrategy()
        patch, _ = strategy.create_patch(env_var_violation, "qa")

        strategy.apply_patch(env_var_violation, patch, "qa", dry_run=True)

        assert len(strategy.applied_patches) == 0


class TestGetDefaultStrategies:
    """Test get_default_strategies function."""

    def test_returns_list(self):
        """Test returns a list of strategies."""
        strategies = get_default_strategies()
        assert isinstance(strategies, list)
        assert len(strategies) > 0

    def test_all_are_strategies(self):
        """Test all items are valid strategies."""
        strategies = get_default_strategies()
        for strategy in strategies:
            assert hasattr(strategy, "name")
            assert hasattr(strategy, "supported_rules")
            assert hasattr(strategy, "can_remediate")
            assert hasattr(strategy, "create_patch")
            assert hasattr(strategy, "apply_patch")

    def test_includes_required_strategies(self):
        """Test includes all required strategy types."""
        strategies = get_default_strategies()
        names = [s.name for s in strategies]

        assert "env-var-fix" in names
        assert "naming-fix" in names
        assert "tag-fix" in names
        assert "hitl-only" in names

    def test_covers_all_rules(self):
        """Test all validation rules have a strategy."""
        strategies = get_default_strategies()
        all_rules = set()
        for strategy in strategies:
            all_rules.update(strategy.supported_rules)

        # Check critical rules are covered
        critical_rules = [
            "ENV-001",
            "ENV-002",
            "ENV-003",
            "ENV-004",
            "ENV-005",
            "ENV-006",
            "ENV-007",
            "ENV-008",
        ]
        for rule in critical_rules:
            assert rule in all_rules, f"Missing strategy for {rule}"

        # Check warning rules are covered
        warning_rules = ["ENV-101", "ENV-102", "ENV-103", "ENV-104"]
        for rule in warning_rules:
            assert rule in all_rules, f"Missing strategy for {rule}"

        # Check info rules are covered
        info_rules = ["ENV-201", "ENV-202"]
        for rule in info_rules:
            assert rule in all_rules, f"Missing strategy for {rule}"
