"""Tests for Environment Validator Remediation Engine (ADR-062 Phase 4)."""

from datetime import datetime

import pytest

from src.services.env_validator.models import Severity, Violation
from src.services.env_validator.remediation_engine import (
    REMEDIATION_SAFETY_MATRIX,
    MockRemediationEngine,
    RemediationAction,
    RemediationEngine,
    RemediationResult,
    RemediationRisk,
    RemediationStatus,
)
from src.services.env_validator.remediation_strategies import (
    MockRemediationStrategy,
    get_default_strategies,
)


# Test fixtures
@pytest.fixture
def env_var_violation():
    """ENV-101 violation (safe to auto-remediate)."""
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
    """ENV-201 violation (low risk, dev/qa only)."""
    return Violation(
        rule_id="ENV-201",
        severity=Severity.INFO,
        resource_type="ConfigMap",
        resource_name="test-config",
        field_path="metadata.name",
        expected_value="aura-test-config",
        actual_value="test-config",
        message="Resource naming convention violation",
        suggested_fix="Rename to aura-test-config",
        auto_remediable=True,
    )


@pytest.fixture
def critical_violation():
    """ENV-001 violation (critical, requires HITL)."""
    return Violation(
        rule_id="ENV-001",
        severity=Severity.CRITICAL,
        resource_type="ConfigMap",
        resource_name="aura-api-config",
        field_path="data.DYNAMODB_TABLE_ARN",
        expected_value="arn:aws:dynamodb:us-east-1:234567890123:table/aura-tasks-qa",
        actual_value="arn:aws:dynamodb:us-east-1:123456789012:table/aura-tasks-dev",
        message="Account ID mismatch in ARN",
        suggested_fix=None,
        auto_remediable=False,
    )


@pytest.fixture
def mock_strategy():
    """Mock strategy for testing."""
    return MockRemediationStrategy(
        name="test-strategy",
        rules=["ENV-101", "ENV-201"],
        can_fix=True,
        risk=RemediationRisk.SAFE,
    )


class TestRemediationStatus:
    """Test RemediationStatus enum."""

    def test_status_values(self):
        """Verify all status values exist."""
        assert RemediationStatus.PENDING == "pending"
        assert RemediationStatus.APPROVED == "approved"
        assert RemediationStatus.IN_PROGRESS == "in_progress"
        assert RemediationStatus.SUCCESS == "success"
        assert RemediationStatus.FAILED == "failed"
        assert RemediationStatus.REJECTED == "rejected"
        assert RemediationStatus.SKIPPED == "skipped"


class TestRemediationRisk:
    """Test RemediationRisk enum."""

    def test_risk_values(self):
        """Verify all risk levels exist."""
        assert RemediationRisk.SAFE == "safe"
        assert RemediationRisk.LOW == "low"
        assert RemediationRisk.MEDIUM == "medium"
        assert RemediationRisk.HIGH == "high"
        assert RemediationRisk.CRITICAL == "critical"


class TestRemediationAction:
    """Test RemediationAction dataclass."""

    def test_action_creation(self, env_var_violation):
        """Test creating a remediation action."""
        action = RemediationAction(
            action_id="rem-test123",
            violation=env_var_violation,
            environment="qa",
            risk_level=RemediationRisk.SAFE,
            status=RemediationStatus.PENDING,
            strategy_name="env-var-fix",
            description="Fix ENVIRONMENT variable",
            patch={"op": "replace", "path": "/data/ENVIRONMENT", "value": "qa"},
        )

        assert action.action_id == "rem-test123"
        assert action.environment == "qa"
        assert action.risk_level == RemediationRisk.SAFE
        assert action.can_auto_execute is True

    def test_action_requires_approval(self, env_var_violation):
        """Test action that requires approval."""
        action = RemediationAction(
            action_id="rem-test456",
            violation=env_var_violation,
            environment="prod",
            risk_level=RemediationRisk.CRITICAL,
            status=RemediationStatus.PENDING,
            strategy_name="hitl-only",
            description="Critical fix requires approval",
            patch={},
            approval_required=True,
        )

        assert action.can_auto_execute is False

    def test_action_approved(self, env_var_violation):
        """Test approved action can auto-execute."""
        action = RemediationAction(
            action_id="rem-test789",
            violation=env_var_violation,
            environment="prod",
            risk_level=RemediationRisk.MEDIUM,
            status=RemediationStatus.APPROVED,
            strategy_name="configmap-fix",
            description="Approved fix",
            patch={},
            approval_required=True,
            approved_by="admin@aenealabs.com",
            approved_at=datetime.utcnow(),
        )

        assert action.can_auto_execute is True

    def test_action_to_dict(self, env_var_violation):
        """Test serialization to dict."""
        action = RemediationAction(
            action_id="rem-dict",
            violation=env_var_violation,
            environment="qa",
            risk_level=RemediationRisk.SAFE,
            status=RemediationStatus.SUCCESS,
            strategy_name="env-var-fix",
            description="Fixed ENVIRONMENT",
            patch={"op": "replace"},
        )

        d = action.to_dict()
        assert d["action_id"] == "rem-dict"
        assert d["environment"] == "qa"
        assert d["risk_level"] == "safe"
        assert d["status"] == "success"
        assert d["violation"]["rule_id"] == "ENV-101"


class TestRemediationResult:
    """Test RemediationResult dataclass."""

    def test_result_creation(self, env_var_violation):
        """Test creating a remediation result."""
        action = RemediationAction(
            action_id="rem-1",
            violation=env_var_violation,
            environment="qa",
            risk_level=RemediationRisk.SAFE,
            status=RemediationStatus.SUCCESS,
            strategy_name="test",
            description="test",
            patch={},
        )

        result = RemediationResult(
            run_id="rem-run-123",
            environment="qa",
            timestamp=datetime.utcnow(),
            actions=[action],
            auto_fixed=1,
        )

        assert result.total_actions == 1
        assert result.auto_fixed == 1
        assert result.success_rate == 100.0

    def test_result_success_rate(self, env_var_violation, naming_violation):
        """Test success rate calculation."""
        actions = [
            RemediationAction(
                action_id=f"rem-{i}",
                violation=v,
                environment="qa",
                risk_level=RemediationRisk.SAFE,
                status=(
                    RemediationStatus.SUCCESS if i == 0 else RemediationStatus.FAILED
                ),
                strategy_name="test",
                description="test",
                patch={},
            )
            for i, v in enumerate([env_var_violation, naming_violation])
        ]

        result = RemediationResult(
            run_id="rem-run-456",
            environment="qa",
            timestamp=datetime.utcnow(),
            actions=actions,
            auto_fixed=1,
            failed=1,
        )

        assert result.total_actions == 2
        assert result.success_rate == 50.0

    def test_result_to_dict(self):
        """Test serialization to dict."""
        result = RemediationResult(
            run_id="rem-run-789",
            environment="dev",
            timestamp=datetime.utcnow(),
            actions=[],
            auto_fixed=0,
        )

        d = result.to_dict()
        assert d["run_id"] == "rem-run-789"
        assert d["environment"] == "dev"
        assert d["total_actions"] == 0
        assert d["success_rate"] == 100.0


class TestSafetyMatrix:
    """Test remediation safety matrix."""

    def test_env_101_is_safe(self):
        """ENV-101 should be safe to auto-remediate."""
        safety = REMEDIATION_SAFETY_MATRIX["ENV-101"]
        assert safety["auto_remediate"] is True
        assert safety["risk_level"] == RemediationRisk.SAFE
        assert "dev" in safety["allowed_environments"]
        assert "prod" in safety["allowed_environments"]

    def test_env_201_is_low_risk(self):
        """ENV-201 should be low risk (dev/qa only)."""
        safety = REMEDIATION_SAFETY_MATRIX["ENV-201"]
        assert safety["auto_remediate"] is True
        assert safety["risk_level"] == RemediationRisk.LOW
        assert "dev" in safety["allowed_environments"]
        assert "qa" in safety["allowed_environments"]
        assert "prod" not in safety["allowed_environments"]

    def test_env_001_is_critical(self):
        """ENV-001 should never auto-remediate."""
        safety = REMEDIATION_SAFETY_MATRIX["ENV-001"]
        assert safety["auto_remediate"] is False
        assert safety["risk_level"] == RemediationRisk.CRITICAL
        assert len(safety["allowed_environments"]) == 0

    def test_all_critical_rules_blocked(self):
        """All security-critical rules should block auto-remediation."""
        critical_rules = [
            "ENV-001",
            "ENV-003",
            "ENV-004",
            "ENV-006",
            "ENV-007",
            "ENV-008",
        ]
        for rule_id in critical_rules:
            safety = REMEDIATION_SAFETY_MATRIX.get(rule_id)
            assert safety is not None, f"Missing safety matrix for {rule_id}"
            assert (
                safety["auto_remediate"] is False
            ), f"{rule_id} should not auto-remediate"
            assert (
                safety["risk_level"] == RemediationRisk.CRITICAL
            ), f"{rule_id} should be critical"


class TestRemediationEngine:
    """Test RemediationEngine class."""

    def test_engine_creation(self, mock_strategy):
        """Test creating remediation engine."""
        engine = RemediationEngine(
            environment="qa",
            strategies=[mock_strategy],
        )

        assert engine.environment == "qa"
        assert len(engine.strategies) == 1
        assert engine.auto_remediate is True
        assert engine.dry_run is False

    def test_register_strategy(self, mock_strategy):
        """Test registering a strategy."""
        engine = RemediationEngine(environment="dev")
        engine.register_strategy(mock_strategy)

        assert mock_strategy in engine.strategies
        assert "ENV-101" in engine._strategy_map
        assert "ENV-201" in engine._strategy_map

    def test_can_auto_remediate_safe(self, env_var_violation, mock_strategy):
        """Test auto-remediation check for safe violation."""
        engine = RemediationEngine(
            environment="qa",
            strategies=[mock_strategy],
        )

        assert engine.can_auto_remediate(env_var_violation) is True

    def test_can_auto_remediate_critical(self, critical_violation):
        """Test auto-remediation blocked for critical violation."""
        engine = RemediationEngine(
            environment="qa",
            strategies=get_default_strategies(),
        )

        assert engine.can_auto_remediate(critical_violation) is False

    def test_can_auto_remediate_env_restricted(self, naming_violation, mock_strategy):
        """Test auto-remediation respects environment restrictions."""
        # In prod, ENV-201 should not auto-remediate
        engine = RemediationEngine(
            environment="prod",
            strategies=[mock_strategy],
        )

        assert engine.can_auto_remediate(naming_violation) is False

    def test_get_risk_level(self, env_var_violation, critical_violation):
        """Test getting risk level for violations."""
        engine = RemediationEngine(environment="qa")

        assert engine.get_risk_level(env_var_violation) == RemediationRisk.SAFE
        assert engine.get_risk_level(critical_violation) == RemediationRisk.CRITICAL

    def test_requires_approval_safe(self, env_var_violation, mock_strategy):
        """Test safe violations don't require approval."""
        engine = RemediationEngine(
            environment="prod",
            strategies=[mock_strategy],
        )

        assert engine.requires_approval(env_var_violation) is False

    def test_requires_approval_critical(self, critical_violation):
        """Test critical violations require approval."""
        engine = RemediationEngine(
            environment="qa",
            strategies=get_default_strategies(),
        )

        assert engine.requires_approval(critical_violation) is True

    def test_create_remediation_action(self, env_var_violation, mock_strategy):
        """Test creating a remediation action."""
        engine = RemediationEngine(
            environment="qa",
            strategies=[mock_strategy],
        )

        action = engine.create_remediation_action(env_var_violation)

        assert action is not None
        assert action.violation == env_var_violation
        assert action.environment == "qa"
        assert action.strategy_name == "test-strategy"
        assert action.status == RemediationStatus.PENDING

    def test_create_action_no_strategy(self, critical_violation):
        """Test creating action with no matching strategy."""
        engine = RemediationEngine(
            environment="qa",
            strategies=[],  # No strategies
        )

        action = engine.create_remediation_action(critical_violation)
        assert action is None

    def test_execute_action(self, env_var_violation, mock_strategy):
        """Test executing a remediation action."""
        engine = RemediationEngine(
            environment="qa",
            strategies=[mock_strategy],
            dry_run=True,
        )

        action = engine.create_remediation_action(env_var_violation)
        executed = engine.execute_action(action)

        assert executed.status == RemediationStatus.SUCCESS
        assert executed.executed_at is not None

    def test_execute_action_requires_approval(self, env_var_violation, mock_strategy):
        """Test execution skipped when approval required."""
        engine = RemediationEngine(
            environment="qa",
            strategies=[mock_strategy],
        )

        action = engine.create_remediation_action(env_var_violation)
        action.approval_required = True
        executed = engine.execute_action(action)

        # Should not have executed
        assert executed.status == RemediationStatus.PENDING

    def test_remediate_violations(
        self, env_var_violation, naming_violation, mock_strategy
    ):
        """Test remediating multiple violations."""
        engine = RemediationEngine(
            environment="qa",
            strategies=[mock_strategy],
            dry_run=True,
        )

        result = engine.remediate_violations([env_var_violation, naming_violation])

        assert result.total_actions == 2
        assert result.auto_fixed == 2
        assert result.failed == 0
        assert result.success_rate == 100.0

    def test_remediate_with_non_auto_remediable(
        self, env_var_violation, critical_violation, mock_strategy
    ):
        """Test remediation skips non-auto-remediable violations."""
        engine = RemediationEngine(
            environment="qa",
            strategies=[mock_strategy],
            dry_run=True,
        )

        result = engine.remediate_violations([env_var_violation, critical_violation])

        # Only env_var_violation should be processed (critical is not auto_remediable)
        assert result.auto_fixed == 1
        assert result.skipped == 1

    def test_approve_action(self, env_var_violation, mock_strategy):
        """Test approving a pending action."""
        engine = RemediationEngine(
            environment="qa",
            strategies=[mock_strategy],
        )

        action = engine.create_remediation_action(env_var_violation)
        actions = [action]

        approved = engine.approve_action(
            action.action_id,
            actions,
            approved_by="admin@aenealabs.com",
        )

        assert approved.status == RemediationStatus.APPROVED
        assert approved.approved_by == "admin@aenealabs.com"
        assert approved.approved_at is not None

    def test_reject_action(self, env_var_violation, mock_strategy):
        """Test rejecting a pending action."""
        engine = RemediationEngine(
            environment="qa",
            strategies=[mock_strategy],
        )

        action = engine.create_remediation_action(env_var_violation)
        actions = [action]

        rejected = engine.reject_action(
            action.action_id,
            actions,
            rejected_by="security@aenealabs.com",
            reason="Not safe to apply automatically",
        )

        assert rejected.status == RemediationStatus.REJECTED
        assert rejected.rejection_reason == "Not safe to apply automatically"


class TestMockRemediationEngine:
    """Test MockRemediationEngine class."""

    def test_mock_engine_is_dry_run(self):
        """Mock engine should always be dry run."""
        engine = MockRemediationEngine(environment="qa")
        assert engine.dry_run is True

    def test_mock_engine_tracks_patches(self, env_var_violation, mock_strategy):
        """Mock engine should track applied patches."""
        engine = MockRemediationEngine(
            environment="qa",
            strategies=[mock_strategy],
        )

        action = engine.create_remediation_action(env_var_violation)
        engine.execute_action(action)

        assert len(engine.applied_patches) == 1
        assert engine.applied_patches[0]["action_id"] == action.action_id

    def test_mock_engine_simulates_success(self, env_var_violation, mock_strategy):
        """Mock engine should simulate successful execution."""
        engine = MockRemediationEngine(
            environment="qa",
            strategies=[mock_strategy],
        )

        action = engine.create_remediation_action(env_var_violation)
        executed = engine.execute_action(action)

        assert executed.status == RemediationStatus.SUCCESS


class TestRemediationEngineIntegration:
    """Integration tests for remediation engine with default strategies."""

    def test_full_remediation_flow_dev(self, env_var_violation, naming_violation):
        """Test full remediation flow in dev environment."""
        engine = RemediationEngine(
            environment="dev",
            strategies=get_default_strategies(),
            dry_run=True,
        )

        violations = [env_var_violation, naming_violation]
        result = engine.remediate_violations(violations)

        # Both should be processed in dev
        assert result.total_actions == 2
        assert result.auto_fixed == 2

    def test_full_remediation_flow_prod(self, env_var_violation, naming_violation):
        """Test full remediation flow in prod environment."""
        engine = RemediationEngine(
            environment="prod",
            strategies=get_default_strategies(),
            dry_run=True,
        )

        violations = [env_var_violation, naming_violation]
        result = engine.remediate_violations(violations)

        # ENV-101 should succeed, ENV-201 should be skipped in prod
        assert result.auto_fixed == 1
        assert result.skipped == 1

    def test_approval_then_execute(self, critical_violation):
        """Test HITL approval workflow."""
        # Create a modified violation that's marked auto_remediable
        violation = Violation(
            rule_id="ENV-001",
            severity=Severity.CRITICAL,
            resource_type="ConfigMap",
            resource_name="test",
            field_path="data.ARN",
            expected_value="correct",
            actual_value="wrong",
            message="Account ID mismatch",
            auto_remediable=True,  # Marked as auto_remediable for testing
        )

        engine = RemediationEngine(
            environment="qa",
            strategies=get_default_strategies(),
            dry_run=True,
        )

        # Create action
        action = engine.create_remediation_action(violation)
        assert action is not None
        assert action.approval_required is True

        # Approve
        actions = [action]
        engine.approve_action(action.action_id, actions, "admin@aenealabs.com")

        # Now execute
        executed = engine.execute_action(action)
        assert executed.status == RemediationStatus.SUCCESS
