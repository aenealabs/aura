"""Auto-remediation engine for Environment Validator (ADR-062 Phase 4).

Orchestrates safe auto-remediation of environment configuration violations
with support for HITL approval workflow for risky fixes.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Protocol

from src.services.env_validator.models import Violation

logger = logging.getLogger(__name__)


class RemediationStatus(str, Enum):
    """Status of a remediation attempt."""

    PENDING = "pending"  # Awaiting execution or approval
    APPROVED = "approved"  # Approved by HITL, ready to execute
    IN_PROGRESS = "in_progress"  # Currently being applied
    SUCCESS = "success"  # Successfully remediated
    FAILED = "failed"  # Remediation attempt failed
    REJECTED = "rejected"  # Rejected by HITL
    SKIPPED = "skipped"  # Skipped (not auto-remediable or disabled)


class RemediationRisk(str, Enum):
    """Risk level of a remediation action."""

    SAFE = "safe"  # Zero risk, can auto-remediate anywhere
    LOW = "low"  # Low risk, auto-remediate in dev/qa only
    MEDIUM = "medium"  # Medium risk, requires HITL in all environments
    HIGH = "high"  # High risk, requires senior approval
    CRITICAL = "critical"  # Security-critical, never auto-remediate


@dataclass
class RemediationAction:
    """A proposed or executed remediation action."""

    action_id: str
    violation: Violation
    environment: str
    risk_level: RemediationRisk
    status: RemediationStatus
    strategy_name: str
    description: str
    patch: dict  # JSON patch or similar
    before_state: Optional[dict] = None
    after_state: Optional[dict] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    executed_by: Optional[str] = None
    approval_required: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def can_auto_execute(self) -> bool:
        """Check if this action can be auto-executed without approval."""
        if self.approval_required:
            return self.status == RemediationStatus.APPROVED
        return self.status == RemediationStatus.PENDING

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "action_id": self.action_id,
            "violation": {
                "rule_id": self.violation.rule_id,
                "severity": self.violation.severity.value,
                "resource_type": self.violation.resource_type,
                "resource_name": self.violation.resource_name,
                "field_path": self.violation.field_path,
                "expected_value": self.violation.expected_value,
                "actual_value": self.violation.actual_value,
            },
            "environment": self.environment,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "strategy_name": self.strategy_name,
            "description": self.description,
            "patch": self.patch,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "executed_by": self.executed_by,
            "approval_required": self.approval_required,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejection_reason": self.rejection_reason,
            "error_message": self.error_message,
        }


@dataclass
class RemediationResult:
    """Result of a remediation execution."""

    run_id: str
    environment: str
    timestamp: datetime
    actions: list[RemediationAction]
    auto_fixed: int = 0
    pending_approval: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def total_actions(self) -> int:
        """Total number of remediation actions."""
        return len(self.actions)

    @property
    def success_rate(self) -> float:
        """Calculate success rate of auto-remediation."""
        if self.total_actions == 0:
            return 100.0
        return (self.auto_fixed / self.total_actions) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "environment": self.environment,
            "timestamp": self.timestamp.isoformat(),
            "total_actions": self.total_actions,
            "auto_fixed": self.auto_fixed,
            "pending_approval": self.pending_approval,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": self.success_rate,
            "actions": [a.to_dict() for a in self.actions],
        }


class RemediationStrategy(Protocol):
    """Protocol for remediation strategies."""

    @property
    def name(self) -> str:
        """Strategy identifier."""
        ...

    @property
    def supported_rules(self) -> list[str]:
        """List of rule IDs this strategy can remediate."""
        ...

    def can_remediate(self, violation: Violation, environment: str) -> bool:
        """Check if this strategy can remediate the violation."""
        ...

    def get_risk_level(self, violation: Violation, environment: str) -> RemediationRisk:
        """Determine the risk level of remediation."""
        ...

    def create_patch(self, violation: Violation, environment: str) -> tuple[dict, str]:
        """Create remediation patch and description.

        Returns:
            Tuple of (patch dict, human-readable description)
        """
        ...

    def apply_patch(
        self, violation: Violation, patch: dict, environment: str, dry_run: bool = False
    ) -> tuple[bool, Optional[str]]:
        """Apply the remediation patch.

        Args:
            violation: The violation to fix
            patch: The patch to apply
            environment: Target environment
            dry_run: If True, validate but don't apply

        Returns:
            Tuple of (success, error_message)
        """
        ...


# Safety matrix per ADR-062
REMEDIATION_SAFETY_MATRIX: dict[str, dict] = {
    # Auto-remediate: YES (zero risk)
    "ENV-101": {
        "auto_remediate": True,
        "risk_level": RemediationRisk.SAFE,
        "justification": "ENVIRONMENT env var is a simple string patch with zero risk",
        "allowed_environments": ["dev", "qa", "staging", "prod"],
    },
    # Auto-remediate: YES (dev/qa only)
    "ENV-201": {
        "auto_remediate": True,
        "risk_level": RemediationRisk.LOW,
        "justification": "Resource suffix is a naming fix, HITL in prod",
        "allowed_environments": ["dev", "qa"],
    },
    "ENV-202": {
        "auto_remediate": True,
        "risk_level": RemediationRisk.LOW,
        "justification": "Tag consistency fix, HITL in prod",
        "allowed_environments": ["dev", "qa"],
    },
    # Auto-remediate: NO (requires HITL)
    "ENV-001": {
        "auto_remediate": False,
        "risk_level": RemediationRisk.CRITICAL,
        "justification": "Account ID changes are security-critical",
        "allowed_environments": [],
    },
    "ENV-002": {
        "auto_remediate": False,
        "risk_level": RemediationRisk.HIGH,
        "justification": "ECR registry change could deploy untested code",
        "allowed_environments": [],
    },
    "ENV-003": {
        "auto_remediate": False,
        "risk_level": RemediationRisk.CRITICAL,
        "justification": "DynamoDB table change could cause data loss",
        "allowed_environments": [],
    },
    "ENV-004": {
        "auto_remediate": False,
        "risk_level": RemediationRisk.CRITICAL,
        "justification": "Neptune/OpenSearch endpoint change is security-critical",
        "allowed_environments": [],
    },
    "ENV-005": {
        "auto_remediate": False,
        "risk_level": RemediationRisk.CRITICAL,
        "justification": "SNS/SQS ARN change affects message routing",
        "allowed_environments": [],
    },
    "ENV-006": {
        "auto_remediate": False,
        "risk_level": RemediationRisk.CRITICAL,
        "justification": "Region change is security-critical (GovCloud)",
        "allowed_environments": [],
    },
    "ENV-007": {
        "auto_remediate": False,
        "risk_level": RemediationRisk.CRITICAL,
        "justification": "KMS key change is security-critical",
        "allowed_environments": [],
    },
    "ENV-008": {
        "auto_remediate": False,
        "risk_level": RemediationRisk.CRITICAL,
        "justification": "IAM role change is security-critical",
        "allowed_environments": [],
    },
    "ENV-102": {
        "auto_remediate": False,
        "risk_level": RemediationRisk.MEDIUM,
        "justification": "Secret path change requires verification",
        "allowed_environments": [],
    },
    "ENV-103": {
        "auto_remediate": False,
        "risk_level": RemediationRisk.MEDIUM,
        "justification": "Log group change requires new resource creation",
        "allowed_environments": [],
    },
    "ENV-104": {
        "auto_remediate": False,
        "risk_level": RemediationRisk.CRITICAL,
        "justification": "IRSA annotation change is security-critical",
        "allowed_environments": [],
    },
}


class RemediationEngine:
    """Orchestrates auto-remediation with safety controls."""

    def __init__(
        self,
        environment: str,
        strategies: Optional[list[RemediationStrategy]] = None,
        auto_remediate: bool = True,
        dry_run: bool = False,
    ):
        """Initialize remediation engine.

        Args:
            environment: Target environment (dev, qa, staging, prod)
            strategies: List of remediation strategies to use
            auto_remediate: If True, automatically apply safe fixes
            dry_run: If True, create actions but don't apply
        """
        self.environment = environment
        self.strategies = strategies or []
        self.auto_remediate = auto_remediate
        self.dry_run = dry_run
        self._strategy_map: dict[str, RemediationStrategy] = {}

        # Build rule -> strategy mapping
        for strategy in self.strategies:
            for rule_id in strategy.supported_rules:
                self._strategy_map[rule_id] = strategy

    def register_strategy(self, strategy: RemediationStrategy) -> None:
        """Register a remediation strategy."""
        self.strategies.append(strategy)
        for rule_id in strategy.supported_rules:
            self._strategy_map[rule_id] = strategy

    def can_auto_remediate(self, violation: Violation) -> bool:
        """Check if a violation can be auto-remediated in this environment."""
        rule_id = violation.rule_id
        safety = REMEDIATION_SAFETY_MATRIX.get(rule_id)

        if not safety:
            logger.warning(f"No safety matrix entry for rule {rule_id}")
            return False

        if not safety["auto_remediate"]:
            return False

        if self.environment not in safety["allowed_environments"]:
            return False

        # Check if we have a strategy for this rule
        if rule_id not in self._strategy_map:
            return False

        strategy = self._strategy_map[rule_id]
        return strategy.can_remediate(violation, self.environment)

    def get_risk_level(self, violation: Violation) -> RemediationRisk:
        """Get the risk level for remediating a violation."""
        rule_id = violation.rule_id
        safety = REMEDIATION_SAFETY_MATRIX.get(rule_id)

        if safety:
            return safety["risk_level"]

        # Default to CRITICAL for unknown rules
        return RemediationRisk.CRITICAL

    def requires_approval(self, violation: Violation) -> bool:
        """Check if remediation requires HITL approval."""
        if not self.can_auto_remediate(violation):
            return True

        risk = self.get_risk_level(violation)

        # Safe risk level can be auto-remediated anywhere
        if risk == RemediationRisk.SAFE:
            return False

        # Low risk requires approval in staging/prod
        if risk == RemediationRisk.LOW:
            return self.environment in ["staging", "prod"]

        # Medium and above always require approval
        return True

    def create_remediation_action(
        self, violation: Violation
    ) -> Optional[RemediationAction]:
        """Create a remediation action for a violation."""
        rule_id = violation.rule_id
        strategy = self._strategy_map.get(rule_id)

        if not strategy:
            logger.info(f"No strategy available for rule {rule_id}")
            return None

        if not strategy.can_remediate(violation, self.environment):
            logger.info(
                f"Strategy {strategy.name} cannot remediate "
                f"{rule_id} in {self.environment}"
            )
            return None

        try:
            patch, description = strategy.create_patch(violation, self.environment)
        except Exception as e:
            logger.error(f"Failed to create patch for {rule_id}: {e}")
            return None

        risk_level = self.get_risk_level(violation)
        requires_approval = self.requires_approval(violation)

        action = RemediationAction(
            action_id=f"rem-{uuid.uuid4().hex[:12]}",
            violation=violation,
            environment=self.environment,
            risk_level=risk_level,
            status=RemediationStatus.PENDING,
            strategy_name=strategy.name,
            description=description,
            patch=patch,
            approval_required=requires_approval,
        )

        return action

    def execute_action(self, action: RemediationAction) -> RemediationAction:
        """Execute a single remediation action."""
        if not action.can_auto_execute:
            logger.info(
                f"Action {action.action_id} requires approval, skipping execution"
            )
            return action

        rule_id = action.violation.rule_id
        strategy = self._strategy_map.get(rule_id)

        if not strategy:
            action.status = RemediationStatus.FAILED
            action.error_message = f"No strategy found for rule {rule_id}"
            return action

        action.status = RemediationStatus.IN_PROGRESS
        action.executed_at = datetime.utcnow()
        action.executed_by = "env-validator-agent" if not self.dry_run else "dry-run"

        try:
            success, error = strategy.apply_patch(
                action.violation,
                action.patch,
                self.environment,
                dry_run=self.dry_run,
            )

            if success:
                action.status = RemediationStatus.SUCCESS
                logger.info(
                    f"Successfully remediated {action.violation.resource_name} "
                    f"({rule_id}) in {self.environment}"
                )
            else:
                action.status = RemediationStatus.FAILED
                action.error_message = error
                logger.error(
                    f"Failed to remediate {action.violation.resource_name}: {error}"
                )

        except Exception as e:
            action.status = RemediationStatus.FAILED
            action.error_message = str(e)
            logger.exception(f"Exception during remediation: {e}")

        return action

    def remediate_violations(self, violations: list[Violation]) -> RemediationResult:
        """Process violations and apply safe remediations.

        Args:
            violations: List of violations to remediate

        Returns:
            RemediationResult with all actions and statistics
        """
        run_id = f"rem-run-{uuid.uuid4().hex[:12]}"
        actions: list[RemediationAction] = []
        auto_fixed = 0
        pending_approval = 0
        failed = 0
        skipped = 0

        for violation in violations:
            # Check if auto-remediable
            if not violation.auto_remediable:
                logger.debug(
                    f"Violation {violation.rule_id} not marked as auto-remediable"
                )
                skipped += 1
                continue

            # Create action
            action = self.create_remediation_action(violation)
            if not action:
                skipped += 1
                continue

            # Execute if auto-remediation is enabled
            if self.auto_remediate and action.can_auto_execute:
                action = self.execute_action(action)

                if action.status == RemediationStatus.SUCCESS:
                    auto_fixed += 1
                elif action.status == RemediationStatus.FAILED:
                    failed += 1
            elif action.approval_required:
                pending_approval += 1
            else:
                skipped += 1

            actions.append(action)

        return RemediationResult(
            run_id=run_id,
            environment=self.environment,
            timestamp=datetime.utcnow(),
            actions=actions,
            auto_fixed=auto_fixed,
            pending_approval=pending_approval,
            failed=failed,
            skipped=skipped,
        )

    def approve_action(
        self, action_id: str, actions: list[RemediationAction], approved_by: str
    ) -> Optional[RemediationAction]:
        """Approve a pending remediation action.

        Args:
            action_id: ID of the action to approve
            actions: List of actions to search
            approved_by: User/system that approved

        Returns:
            Updated action or None if not found
        """
        # O(1) lookup by action_id instead of linear scan
        action_map = {a.action_id: a for a in actions}
        action = action_map.get(action_id)
        if action is None:
            return None

        if action.status != RemediationStatus.PENDING:
            logger.warning(
                f"Action {action_id} is not pending, status: {action.status}"
            )
            return action

        action.status = RemediationStatus.APPROVED
        action.approved_by = approved_by
        action.approved_at = datetime.utcnow()
        return action

    def reject_action(
        self,
        action_id: str,
        actions: list[RemediationAction],
        rejected_by: str,
        reason: str,
    ) -> Optional[RemediationAction]:
        """Reject a pending remediation action.

        Args:
            action_id: ID of the action to reject
            actions: List of actions to search
            rejected_by: User/system that rejected
            reason: Rejection reason

        Returns:
            Updated action or None if not found
        """
        # O(1) lookup by action_id instead of linear scan
        action_map = {a.action_id: a for a in actions}
        action = action_map.get(action_id)
        if action is None:
            return None

        if action.status != RemediationStatus.PENDING:
            logger.warning(
                f"Action {action_id} is not pending, status: {action.status}"
            )
            return action

        action.status = RemediationStatus.REJECTED
        action.rejection_reason = reason
        action.executed_by = rejected_by
        action.executed_at = datetime.utcnow()
        return action


class MockRemediationEngine(RemediationEngine):
    """Mock remediation engine for testing without K8s access."""

    def __init__(
        self,
        environment: str = "dev",
        strategies: Optional[list[RemediationStrategy]] = None,
        auto_remediate: bool = True,
    ):
        """Initialize mock engine (always dry_run=True)."""
        super().__init__(
            environment=environment,
            strategies=strategies or [],
            auto_remediate=auto_remediate,
            dry_run=True,  # Mock always uses dry run
        )
        self._applied_patches: list[dict] = []

    def execute_action(self, action: RemediationAction) -> RemediationAction:
        """Mock execution that simulates success."""
        if not action.can_auto_execute:
            return action

        action.status = RemediationStatus.IN_PROGRESS
        action.executed_at = datetime.utcnow()
        action.executed_by = "mock-engine"

        # Simulate successful application
        self._applied_patches.append(
            {
                "action_id": action.action_id,
                "patch": action.patch,
                "environment": self.environment,
            }
        )

        action.status = RemediationStatus.SUCCESS
        return action

    @property
    def applied_patches(self) -> list[dict]:
        """Get list of patches that would have been applied."""
        return self._applied_patches
