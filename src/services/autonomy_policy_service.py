"""
Project Aura - Autonomy Policy Service

Provides runtime enforcement and DynamoDB persistence of autonomy policies,
enabling organizations and users to configure HITL requirements as optional
based on their compliance and risk tolerance needs.

This service enables Aura to achieve 85% autonomous operation for commercial
enterprises while maintaining full HITL capability for regulated industries.

Key Features:
- Per-organization autonomy policy persistence (DynamoDB)
- Configurable HITL toggle (enable/disable by severity, operation, repository)
- Industry presets (defense, fintech, enterprise, fully_autonomous)
- Guardrails that cannot be overridden (production_deployment, credential_modification)
- Audit logging for all policy changes and autonomous decisions

Usage:
    >>> service = AutonomyPolicyService(mode=AutonomyServiceMode.AWS)
    >>> policy = service.create_policy(
    ...     organization_id="org-123",
    ...     default_level=AutonomyLevel.CRITICAL_HITL,
    ...     hitl_enabled=True
    ... )
    >>> # Check if HITL is required for a specific operation
    >>> requires_hitl = service.requires_hitl_approval(
    ...     policy_id="policy-123",
    ...     severity="HIGH",
    ...     operation="security_patch"
    ... )
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Boto3 imports (available in AWS environment)
try:
    import boto3
    from boto3.dynamodb.conditions import Attr, Key

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("Boto3 not available - using mock mode")


# =============================================================================
# Enums
# =============================================================================


class AutonomyLevel(Enum):
    """Defines how much human oversight is required."""

    FULL_HITL = "full_hitl"  # All actions require approval
    CRITICAL_HITL = "critical_hitl"  # Only CRITICAL/HIGH severity requires approval
    AUDIT_ONLY = "audit_only"  # No approval needed, but all actions logged
    FULL_AUTONOMOUS = "full_autonomous"  # No approval, minimal logging


class AutonomyServiceMode(Enum):
    """Operating modes for autonomy policy service."""

    MOCK = "mock"  # In-memory storage for testing
    AWS = "aws"  # Real DynamoDB


class PolicyChangeType(Enum):
    """Types of policy changes for audit logging."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    HITL_TOGGLED = "hitl_toggled"
    LEVEL_CHANGED = "level_changed"
    OVERRIDE_ADDED = "override_added"
    OVERRIDE_REMOVED = "override_removed"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AutonomyOverride:
    """Override for specific context (severity, operation, or repository)."""

    context_type: str  # "severity", "operation", "repository"
    context_value: str  # e.g., "HIGH", "production_deployment", "org/repo"
    autonomy_level: AutonomyLevel
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    created_by: str | None = None
    reason: str | None = None


@dataclass
class AutonomyPolicy:
    """
    Organization-specific autonomy configuration with persistence support.

    Attributes:
        policy_id: Unique identifier for this policy
        organization_id: Organization this policy belongs to
        name: Human-readable policy name
        description: Policy description
        hitl_enabled: Master toggle for HITL requirement
        default_level: Default autonomy level when no overrides match
        severity_overrides: Override autonomy by severity level
        operation_overrides: Override autonomy by operation type
        repository_overrides: Override autonomy by repository
        guardrails: Operations that ALWAYS require HITL (cannot be overridden)
        created_at: Timestamp when policy was created
        updated_at: Timestamp of last update
        created_by: User who created the policy
        updated_by: User who last updated the policy
        is_active: Whether this policy is currently active
        preset_name: If created from preset, the preset name
        metadata: Additional configuration metadata
    """

    policy_id: str
    organization_id: str
    name: str = "Default Policy"
    description: str = ""
    hitl_enabled: bool = True  # Master toggle - can be disabled for full autonomy
    default_level: AutonomyLevel = AutonomyLevel.CRITICAL_HITL
    severity_overrides: dict[str, AutonomyLevel] = field(default_factory=dict)
    operation_overrides: dict[str, AutonomyLevel] = field(default_factory=dict)
    repository_overrides: dict[str, AutonomyLevel] = field(default_factory=dict)
    guardrails: list[str] = field(
        default_factory=lambda: [
            "production_deployment",
            "credential_modification",
            "access_control_change",
            "database_migration",
            "infrastructure_change",
        ]
    )
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    created_by: str | None = None
    updated_by: str | None = None
    is_active: bool = True
    preset_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_autonomy_level(
        self,
        severity: str,
        operation: str,
        repository: str = "",
    ) -> AutonomyLevel:
        """
        Determine autonomy level for a specific action.

        Priority order:
        1. Guardrails (always FULL_HITL)
        2. Operation-specific override
        3. Repository-specific override
        4. Severity-specific override
        5. Default level
        """
        # Check guardrails first (cannot be bypassed)
        if operation in self.guardrails:
            return AutonomyLevel.FULL_HITL

        # Check operation-specific override
        if operation in self.operation_overrides:
            return self.operation_overrides[operation]

        # Check repository-specific override
        if repository and repository in self.repository_overrides:
            return self.repository_overrides[repository]

        # Check severity-specific override
        severity_upper = severity.upper()
        if severity_upper in self.severity_overrides:
            return self.severity_overrides[severity_upper]

        # Fall back to default
        return self.default_level

    def requires_hitl(
        self,
        severity: str,
        operation: str,
        repository: str = "",
    ) -> bool:
        """
        Determine if HITL approval is required for a specific action.

        Returns True if:
        - hitl_enabled is True AND autonomy level is FULL_HITL
        - hitl_enabled is True AND autonomy level is CRITICAL_HITL and severity is HIGH/CRITICAL

        Returns False if:
        - hitl_enabled is False (master toggle off)
        - Autonomy level is AUDIT_ONLY or FULL_AUTONOMOUS
        """
        # Master toggle check
        if not self.hitl_enabled:
            # Even with HITL disabled, guardrails still apply
            if operation in self.guardrails:
                return True
            return False

        # Get autonomy level for this context
        level = self.get_autonomy_level(severity, operation, repository)

        if level == AutonomyLevel.FULL_HITL:
            return True

        if level == AutonomyLevel.CRITICAL_HITL:
            return severity.upper() in ("HIGH", "CRITICAL")

        # AUDIT_ONLY and FULL_AUTONOMOUS don't require HITL
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert policy to dictionary for DynamoDB storage."""
        return {
            "policy_id": self.policy_id,
            "organization_id": self.organization_id,
            "name": self.name,
            "description": self.description,
            "hitl_enabled": self.hitl_enabled,
            "default_level": self.default_level.value,
            "severity_overrides": {
                k: v.value for k, v in self.severity_overrides.items()
            },
            "operation_overrides": {
                k: v.value for k, v in self.operation_overrides.items()
            },
            "repository_overrides": {
                k: v.value for k, v in self.repository_overrides.items()
            },
            "guardrails": self.guardrails,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "is_active": self.is_active,
            "preset_name": self.preset_name,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutonomyPolicy":
        """Create policy from DynamoDB item."""
        return cls(
            policy_id=data["policy_id"],
            organization_id=data["organization_id"],
            name=data.get("name", "Default Policy"),
            description=data.get("description", ""),
            hitl_enabled=data.get("hitl_enabled", True),
            default_level=AutonomyLevel(data.get("default_level", "critical_hitl")),
            severity_overrides={
                k: AutonomyLevel(v)
                for k, v in data.get("severity_overrides", {}).items()
            },
            operation_overrides={
                k: AutonomyLevel(v)
                for k, v in data.get("operation_overrides", {}).items()
            },
            repository_overrides={
                k: AutonomyLevel(v)
                for k, v in data.get("repository_overrides", {}).items()
            },
            guardrails=data.get(
                "guardrails",
                [
                    "production_deployment",
                    "credential_modification",
                    "access_control_change",
                    "database_migration",
                    "infrastructure_change",
                ],
            ),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            created_by=data.get("created_by"),
            updated_by=data.get("updated_by"),
            is_active=data.get("is_active", True),
            preset_name=data.get("preset_name"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_preset(cls, preset_name: str, organization_id: str) -> "AutonomyPolicy":
        """
        Create an AutonomyPolicy from a named preset.

        Available presets:
        - defense_contractor: FULL_HITL default (GovCloud, CMMC compliance)
        - financial_services: FULL_HITL default (SOX, PCI-DSS compliance)
        - healthcare: FULL_HITL default (HIPAA compliance)
        - fintech_startup: CRITICAL_HITL with AUDIT_ONLY for LOW/MEDIUM
        - enterprise_standard: CRITICAL_HITL with FULL_AUTONOMOUS for LOW
        - internal_tools: FULL_AUTONOMOUS with guardrails
        - fully_autonomous: FULL_AUTONOMOUS with guardrails (commercial dev/test)
        """
        policy_id = f"policy-{uuid.uuid4().hex[:12]}"

        presets = {
            "defense_contractor": cls(
                policy_id=policy_id,
                organization_id=organization_id,
                name="Defense Contractor Policy",
                description="Maximum oversight for CMMC Level 3+ compliance",
                hitl_enabled=True,
                default_level=AutonomyLevel.FULL_HITL,
                severity_overrides={"LOW": AutonomyLevel.CRITICAL_HITL},
                preset_name="defense_contractor",
            ),
            "financial_services": cls(
                policy_id=policy_id,
                organization_id=organization_id,
                name="Financial Services Policy",
                description="High oversight for SOX/PCI-DSS compliance",
                hitl_enabled=True,
                default_level=AutonomyLevel.FULL_HITL,
                severity_overrides={"LOW": AutonomyLevel.AUDIT_ONLY},
                preset_name="financial_services",
            ),
            "healthcare": cls(
                policy_id=policy_id,
                organization_id=organization_id,
                name="Healthcare Policy",
                description="High oversight for HIPAA compliance",
                hitl_enabled=True,
                default_level=AutonomyLevel.FULL_HITL,
                severity_overrides={"LOW": AutonomyLevel.AUDIT_ONLY},
                preset_name="healthcare",
            ),
            "fintech_startup": cls(
                policy_id=policy_id,
                organization_id=organization_id,
                name="Fintech Startup Policy",
                description="Balanced autonomy with HITL for critical issues",
                hitl_enabled=True,
                default_level=AutonomyLevel.CRITICAL_HITL,
                severity_overrides={
                    "LOW": AutonomyLevel.AUDIT_ONLY,
                    "MEDIUM": AutonomyLevel.AUDIT_ONLY,
                },
                preset_name="fintech_startup",
            ),
            "enterprise_standard": cls(
                policy_id=policy_id,
                organization_id=organization_id,
                name="Enterprise Standard Policy",
                description="Standard enterprise autonomy with oversight for critical",
                hitl_enabled=True,
                default_level=AutonomyLevel.CRITICAL_HITL,
                severity_overrides={
                    "LOW": AutonomyLevel.FULL_AUTONOMOUS,
                    "MEDIUM": AutonomyLevel.AUDIT_ONLY,
                },
                preset_name="enterprise_standard",
            ),
            "internal_tools": cls(
                policy_id=policy_id,
                organization_id=organization_id,
                name="Internal Tools Policy",
                description="High autonomy for internal tooling",
                hitl_enabled=True,
                default_level=AutonomyLevel.FULL_AUTONOMOUS,
                operation_overrides={
                    "credential_modification": AutonomyLevel.FULL_HITL,
                    "production_deployment": AutonomyLevel.CRITICAL_HITL,
                },
                preset_name="internal_tools",
            ),
            "fully_autonomous": cls(
                policy_id=policy_id,
                organization_id=organization_id,
                name="Fully Autonomous Policy",
                description="Maximum autonomy for commercial dev/test environments",
                hitl_enabled=False,  # Master toggle OFF
                default_level=AutonomyLevel.FULL_AUTONOMOUS,
                preset_name="fully_autonomous",
                # Guardrails still apply even with hitl_enabled=False
            ),
        }

        if preset_name not in presets:
            raise ValueError(
                f"Unknown preset: {preset_name}. Available: {list(presets.keys())}"
            )

        return presets[preset_name]


@dataclass
class PolicyAuditEntry:
    """Audit log entry for policy changes."""

    audit_id: str
    policy_id: str
    organization_id: str
    change_type: PolicyChangeType
    changed_by: str | None
    changed_at: str
    previous_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    reason: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass
class AutonomyDecision:
    """Record of an autonomous decision made by the system."""

    decision_id: str
    policy_id: str
    organization_id: str
    execution_id: str
    severity: str
    operation: str
    repository: str
    autonomy_level: AutonomyLevel
    hitl_required: bool
    hitl_bypassed: bool  # True if hitl_enabled=False bypassed normal HITL
    auto_approved: bool
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Service
# =============================================================================


class AutonomyPolicyService:
    """
    DynamoDB-backed service for managing autonomy policies.

    Features:
    - Create and manage organization autonomy policies
    - Toggle HITL on/off for different contexts
    - Query policies by organization, preset, or status
    - Full audit trail for compliance
    - Cache for high-performance policy lookups
    """

    # TTL for audit records: 365 days
    AUDIT_TTL_DAYS = 365
    # TTL for decision records: 90 days
    DECISION_TTL_DAYS = 90
    # Cache TTL: 5 minutes
    CACHE_TTL_SECONDS = 300

    def __init__(
        self,
        mode: AutonomyServiceMode = AutonomyServiceMode.MOCK,
        policy_table_name: str | None = None,
        audit_table_name: str | None = None,
        decision_table_name: str | None = None,
        region: str | None = None,
    ):
        """
        Initialize Autonomy Policy Service.

        Args:
            mode: Operating mode (MOCK or AWS)
            policy_table_name: DynamoDB table for policies
            audit_table_name: DynamoDB table for audit logs
            decision_table_name: DynamoDB table for decisions
            region: AWS region
        """
        self.mode = mode
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

        env = os.environ.get("ENVIRONMENT", "dev")
        self.policy_table_name = policy_table_name or f"aura-autonomy-policies-{env}"
        self.audit_table_name = audit_table_name or f"aura-policy-audit-{env}"
        self.decision_table_name = (
            decision_table_name or f"aura-autonomy-decisions-{env}"
        )

        # In-memory storage for mock mode
        self._mock_policies: dict[str, AutonomyPolicy] = {}
        self._mock_audit: list[PolicyAuditEntry] = []
        self._mock_decisions: list[AutonomyDecision] = []

        # Policy cache
        self._policy_cache: dict[str, tuple[AutonomyPolicy, float]] = {}

        # Initialize DynamoDB client if AWS mode
        self._dynamodb: Any = None
        self._policy_table: Any = None
        self._audit_table: Any = None
        self._decision_table: Any = None

        if mode == AutonomyServiceMode.AWS and BOTO3_AVAILABLE:
            self._init_dynamodb()

    def _init_dynamodb(self) -> None:
        """Initialize DynamoDB resources."""
        try:
            dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self._dynamodb = dynamodb
            self._policy_table = dynamodb.Table(self.policy_table_name)
            self._audit_table = dynamodb.Table(self.audit_table_name)
            self._decision_table = dynamodb.Table(self.decision_table_name)
            logger.info(
                f"Initialized DynamoDB tables: {self.policy_table_name}, "
                f"{self.audit_table_name}, {self.decision_table_name}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB: {e}")
            self.mode = AutonomyServiceMode.MOCK

    # =========================================================================
    # Policy CRUD Operations
    # =========================================================================

    def create_policy(
        self,
        organization_id: str,
        name: str = "Default Policy",
        description: str = "",
        hitl_enabled: bool = True,
        default_level: AutonomyLevel = AutonomyLevel.CRITICAL_HITL,
        created_by: str | None = None,
        preset_name: str | None = None,
    ) -> AutonomyPolicy:
        """
        Create a new autonomy policy for an organization.

        Args:
            organization_id: Organization identifier
            name: Human-readable policy name
            description: Policy description
            hitl_enabled: Master toggle for HITL requirement
            default_level: Default autonomy level
            created_by: User creating the policy
            preset_name: Optional preset to base policy on

        Returns:
            Created AutonomyPolicy
        """
        if preset_name:
            policy = AutonomyPolicy.from_preset(preset_name, organization_id)
            policy.name = name or policy.name
            policy.description = description or policy.description
            policy.hitl_enabled = hitl_enabled
            policy.created_by = created_by
        else:
            policy = AutonomyPolicy(
                policy_id=f"policy-{uuid.uuid4().hex[:12]}",
                organization_id=organization_id,
                name=name,
                description=description,
                hitl_enabled=hitl_enabled,
                default_level=default_level,
                created_by=created_by,
            )

        # Persist policy
        self._save_policy(policy)

        # Log creation
        self._log_audit(
            policy_id=policy.policy_id,
            organization_id=organization_id,
            change_type=PolicyChangeType.CREATED,
            changed_by=created_by,
            new_value=policy.to_dict(),
        )

        logger.info(
            f"Created autonomy policy {policy.policy_id} for org {organization_id}"
        )
        return policy

    def create_policy_from_preset(
        self,
        organization_id: str,
        preset_name: str,
        created_by: str | None = None,
    ) -> AutonomyPolicy:
        """
        Create a policy from a named preset.

        Args:
            organization_id: Organization identifier
            preset_name: Name of the preset to use
            created_by: User creating the policy

        Returns:
            Created AutonomyPolicy
        """
        return self.create_policy(
            organization_id=organization_id,
            preset_name=preset_name,
            created_by=created_by,
        )

    def get_policy(self, policy_id: str) -> AutonomyPolicy | None:
        """
        Get a policy by ID.

        Args:
            policy_id: Policy identifier

        Returns:
            AutonomyPolicy if found, None otherwise
        """
        # Check cache first
        cached = self._get_from_cache(policy_id)
        if cached:
            return cached

        # Fetch from storage
        policy = self._fetch_policy(policy_id)
        if policy:
            self._add_to_cache(policy)

        return policy

    def get_policy_for_organization(
        self, organization_id: str
    ) -> AutonomyPolicy | None:
        """
        Get the active policy for an organization.

        Args:
            organization_id: Organization identifier

        Returns:
            Active AutonomyPolicy if found, None otherwise
        """
        if self.mode == AutonomyServiceMode.MOCK:
            for policy in self._mock_policies.values():
                if policy.organization_id == organization_id and policy.is_active:
                    return policy
        # AWS mode - query by organization_id GSI
        elif self._policy_table:
            try:
                response = self._policy_table.query(
                    IndexName="organization-index",
                    KeyConditionExpression=Key("organization_id").eq(organization_id),
                    FilterExpression=Attr("is_active").eq(True),
                )
                items = response.get("Items", [])
                if items:
                    return AutonomyPolicy.from_dict(items[0])
            except Exception as e:
                logger.error(f"Failed to get policy for org {organization_id}: {e}")

        return None

    def update_policy(
        self,
        policy_id: str,
        updates: dict[str, Any],
        updated_by: str | None = None,
        reason: str | None = None,
    ) -> AutonomyPolicy | None:
        """
        Update an existing policy.

        Args:
            policy_id: Policy identifier
            updates: Dictionary of fields to update
            updated_by: User making the update
            reason: Reason for the update

        Returns:
            Updated AutonomyPolicy if successful, None otherwise
        """
        policy = self.get_policy(policy_id)
        if not policy:
            logger.warning(f"Policy {policy_id} not found for update")
            return None

        previous_value = policy.to_dict()

        # Apply updates
        for key, value in updates.items():
            if hasattr(policy, key):
                if key == "default_level" and isinstance(value, str):
                    value = AutonomyLevel(value)
                elif key in (
                    "severity_overrides",
                    "operation_overrides",
                    "repository_overrides",
                ):
                    # Convert string values to AutonomyLevel
                    if isinstance(value, dict):
                        value = {
                            k: AutonomyLevel(v) if isinstance(v, str) else v
                            for k, v in value.items()
                        }
                setattr(policy, key, value)

        policy.updated_at = datetime.now().isoformat()
        policy.updated_by = updated_by

        # Persist changes
        self._save_policy(policy)

        # Invalidate cache
        self._invalidate_cache(policy_id)

        # Determine change type
        change_type = PolicyChangeType.UPDATED
        if "hitl_enabled" in updates:
            change_type = PolicyChangeType.HITL_TOGGLED
        elif "default_level" in updates:
            change_type = PolicyChangeType.LEVEL_CHANGED

        # Log audit
        self._log_audit(
            policy_id=policy_id,
            organization_id=policy.organization_id,
            change_type=change_type,
            changed_by=updated_by,
            previous_value=previous_value,
            new_value=policy.to_dict(),
            reason=reason,
        )

        logger.info(f"Updated policy {policy_id} by {updated_by}")
        return policy

    def toggle_hitl(
        self,
        policy_id: str,
        hitl_enabled: bool,
        updated_by: str | None = None,
        reason: str | None = None,
    ) -> AutonomyPolicy | None:
        """
        Toggle HITL on/off for a policy.

        This is the master switch for enabling/disabling HITL requirements.
        When hitl_enabled=False, only guardrails will still require HITL.

        Args:
            policy_id: Policy identifier
            hitl_enabled: New HITL enabled state
            updated_by: User making the change
            reason: Reason for the change

        Returns:
            Updated AutonomyPolicy if successful, None otherwise
        """
        return self.update_policy(
            policy_id=policy_id,
            updates={"hitl_enabled": hitl_enabled},
            updated_by=updated_by,
            reason=reason or f"HITL {'enabled' if hitl_enabled else 'disabled'}",
        )

    def add_override(
        self,
        policy_id: str,
        override_type: str,  # "severity", "operation", "repository"
        context_value: str,
        autonomy_level: AutonomyLevel,
        updated_by: str | None = None,
        reason: str | None = None,
    ) -> AutonomyPolicy | None:
        """
        Add an override to a policy.

        Args:
            policy_id: Policy identifier
            override_type: Type of override ("severity", "operation", "repository")
            context_value: Value to match (e.g., "HIGH", "production_deployment")
            autonomy_level: Autonomy level for this context
            updated_by: User making the change
            reason: Reason for the change

        Returns:
            Updated AutonomyPolicy if successful, None otherwise
        """
        policy = self.get_policy(policy_id)
        if not policy:
            return None

        override_map = {
            "severity": "severity_overrides",
            "operation": "operation_overrides",
            "repository": "repository_overrides",
        }

        if override_type not in override_map:
            raise ValueError(f"Invalid override type: {override_type}")

        field_name = override_map[override_type]
        overrides = getattr(policy, field_name).copy()
        overrides[context_value] = autonomy_level

        return self.update_policy(
            policy_id=policy_id,
            updates={field_name: overrides},
            updated_by=updated_by,
            reason=reason or f"Added {override_type} override for {context_value}",
        )

    def remove_override(
        self,
        policy_id: str,
        override_type: str,
        context_value: str,
        updated_by: str | None = None,
        reason: str | None = None,
    ) -> AutonomyPolicy | None:
        """
        Remove an override from a policy.

        Args:
            policy_id: Policy identifier
            override_type: Type of override ("severity", "operation", "repository")
            context_value: Value to remove
            updated_by: User making the change
            reason: Reason for the change

        Returns:
            Updated AutonomyPolicy if successful, None otherwise
        """
        policy = self.get_policy(policy_id)
        if not policy:
            return None

        override_map = {
            "severity": "severity_overrides",
            "operation": "operation_overrides",
            "repository": "repository_overrides",
        }

        if override_type not in override_map:
            raise ValueError(f"Invalid override type: {override_type}")

        field_name = override_map[override_type]
        overrides = getattr(policy, field_name).copy()
        overrides.pop(context_value, None)

        return self.update_policy(
            policy_id=policy_id,
            updates={field_name: overrides},
            updated_by=updated_by,
            reason=reason or f"Removed {override_type} override for {context_value}",
        )

    def delete_policy(
        self,
        policy_id: str,
        deleted_by: str | None = None,
        reason: str | None = None,
    ) -> bool:
        """
        Delete (deactivate) a policy.

        Args:
            policy_id: Policy identifier
            deleted_by: User deleting the policy
            reason: Reason for deletion

        Returns:
            True if successful, False otherwise
        """
        policy = self.get_policy(policy_id)
        if not policy:
            return False

        previous_value = policy.to_dict()
        policy.is_active = False
        policy.updated_at = datetime.now().isoformat()
        policy.updated_by = deleted_by

        self._save_policy(policy)
        self._invalidate_cache(policy_id)

        self._log_audit(
            policy_id=policy_id,
            organization_id=policy.organization_id,
            change_type=PolicyChangeType.DELETED,
            changed_by=deleted_by,
            previous_value=previous_value,
            reason=reason,
        )

        logger.info(f"Deleted policy {policy_id} by {deleted_by}")
        return True

    # =========================================================================
    # Decision Operations
    # =========================================================================

    def requires_hitl_approval(
        self,
        policy_id: str,
        severity: str,
        operation: str,
        repository: str = "",
    ) -> bool:
        """
        Check if HITL approval is required for a specific action.

        Args:
            policy_id: Policy identifier
            severity: Action severity (CRITICAL, HIGH, MEDIUM, LOW)
            operation: Operation type
            repository: Repository (optional)

        Returns:
            True if HITL approval is required, False otherwise
        """
        policy = self.get_policy(policy_id)
        if not policy:
            # Default to requiring HITL if policy not found
            logger.warning(f"Policy {policy_id} not found, defaulting to HITL required")
            return True

        return policy.requires_hitl(severity, operation, repository)

    def record_autonomous_decision(
        self,
        policy_id: str,
        execution_id: str,
        severity: str,
        operation: str,
        repository: str,
        autonomy_level: AutonomyLevel,
        hitl_required: bool,
        hitl_bypassed: bool,
        auto_approved: bool,
        metadata: dict[str, Any] | None = None,
    ) -> AutonomyDecision:
        """
        Record an autonomous decision for audit purposes.

        Args:
            policy_id: Policy that was applied
            execution_id: Execution identifier
            severity: Action severity
            operation: Operation type
            repository: Repository
            autonomy_level: Autonomy level that was applied
            hitl_required: Whether HITL was required
            hitl_bypassed: Whether normal HITL was bypassed due to hitl_enabled=False
            auto_approved: Whether the action was auto-approved
            metadata: Additional context

        Returns:
            Created AutonomyDecision
        """
        policy = self.get_policy(policy_id)
        organization_id = policy.organization_id if policy else "unknown"

        decision = AutonomyDecision(
            decision_id=f"decision-{uuid.uuid4().hex[:12]}",
            policy_id=policy_id,
            organization_id=organization_id,
            execution_id=execution_id,
            severity=severity,
            operation=operation,
            repository=repository,
            autonomy_level=autonomy_level,
            hitl_required=hitl_required,
            hitl_bypassed=hitl_bypassed,
            auto_approved=auto_approved,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {},
        )

        self._save_decision(decision)

        logger.info(
            f"Recorded decision {decision.decision_id}: "
            f"hitl_required={hitl_required}, auto_approved={auto_approved}"
        )

        return decision

    def get_decisions_for_execution(self, execution_id: str) -> list[AutonomyDecision]:
        """Get all decisions for a specific execution."""
        if self.mode == AutonomyServiceMode.MOCK:
            return [d for d in self._mock_decisions if d.execution_id == execution_id]

        if self._decision_table:
            try:
                response = self._decision_table.query(
                    IndexName="execution-index",
                    KeyConditionExpression=Key("execution_id").eq(execution_id),
                )
                return [
                    self._decision_from_dict(item) for item in response.get("Items", [])
                ]
            except Exception as e:
                logger.error(
                    f"Failed to get decisions for execution {execution_id}: {e}"
                )

        return []

    # =========================================================================
    # Query Operations
    # =========================================================================

    def list_policies(
        self,
        organization_id: str | None = None,
        include_inactive: bool = False,
    ) -> list[AutonomyPolicy]:
        """
        List policies, optionally filtered by organization.

        Args:
            organization_id: Filter by organization (optional)
            include_inactive: Include deactivated policies

        Returns:
            List of AutonomyPolicy objects
        """
        if self.mode == AutonomyServiceMode.MOCK:
            policies = list(self._mock_policies.values())
            if organization_id:
                policies = [p for p in policies if p.organization_id == organization_id]
            if not include_inactive:
                policies = [p for p in policies if p.is_active]
            return policies

        if self._policy_table:
            try:
                if organization_id:
                    response = self._policy_table.query(
                        IndexName="organization-index",
                        KeyConditionExpression=Key("organization_id").eq(
                            organization_id
                        ),
                    )
                else:
                    response = self._policy_table.scan()

                policies = [
                    AutonomyPolicy.from_dict(item) for item in response.get("Items", [])
                ]

                if not include_inactive:
                    policies = [p for p in policies if p.is_active]

                return policies

            except Exception as e:
                logger.error(f"Failed to list policies: {e}")

        return []

    def get_audit_log(
        self,
        policy_id: str | None = None,
        organization_id: str | None = None,
        limit: int = 100,
    ) -> list[PolicyAuditEntry]:
        """
        Get audit log entries.

        Args:
            policy_id: Filter by policy (optional)
            organization_id: Filter by organization (optional)
            limit: Maximum entries to return

        Returns:
            List of PolicyAuditEntry objects
        """
        if self.mode == AutonomyServiceMode.MOCK:
            entries = self._mock_audit.copy()
            if policy_id:
                entries = [e for e in entries if e.policy_id == policy_id]
            if organization_id:
                entries = [e for e in entries if e.organization_id == organization_id]
            return entries[-limit:]

        # AWS implementation would query the audit table
        return []

    def get_available_presets(self) -> list[dict[str, Any]]:
        """
        Get list of available policy presets.

        Returns:
            List of preset info dictionaries
        """
        return [
            {
                "name": "defense_contractor",
                "display_name": "Defense Contractor",
                "description": "Maximum oversight for CMMC Level 3+ compliance",
                "default_level": "full_hitl",
                "hitl_enabled": True,
            },
            {
                "name": "financial_services",
                "display_name": "Financial Services",
                "description": "High oversight for SOX/PCI-DSS compliance",
                "default_level": "full_hitl",
                "hitl_enabled": True,
            },
            {
                "name": "healthcare",
                "display_name": "Healthcare",
                "description": "High oversight for HIPAA compliance",
                "default_level": "full_hitl",
                "hitl_enabled": True,
            },
            {
                "name": "fintech_startup",
                "display_name": "Fintech Startup",
                "description": "Balanced autonomy with HITL for critical issues",
                "default_level": "critical_hitl",
                "hitl_enabled": True,
            },
            {
                "name": "enterprise_standard",
                "display_name": "Enterprise Standard",
                "description": "Standard enterprise autonomy with oversight for critical",
                "default_level": "critical_hitl",
                "hitl_enabled": True,
            },
            {
                "name": "internal_tools",
                "display_name": "Internal Tools",
                "description": "High autonomy for internal tooling",
                "default_level": "full_autonomous",
                "hitl_enabled": True,
            },
            {
                "name": "fully_autonomous",
                "display_name": "Fully Autonomous",
                "description": "Maximum autonomy for commercial dev/test environments",
                "default_level": "full_autonomous",
                "hitl_enabled": False,
            },
        ]

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _save_policy(self, policy: AutonomyPolicy) -> None:
        """Save policy to storage."""
        if self.mode == AutonomyServiceMode.MOCK:
            self._mock_policies[policy.policy_id] = policy
        elif self._policy_table:
            try:
                self._policy_table.put_item(Item=policy.to_dict())
            except Exception as e:
                logger.error(f"Failed to save policy {policy.policy_id}: {e}")

    def _fetch_policy(self, policy_id: str) -> AutonomyPolicy | None:
        """Fetch policy from storage."""
        if self.mode == AutonomyServiceMode.MOCK:
            return self._mock_policies.get(policy_id)
        elif self._policy_table:
            try:
                response = self._policy_table.get_item(Key={"policy_id": policy_id})
                item = response.get("Item")
                if item:
                    return AutonomyPolicy.from_dict(item)
            except Exception as e:
                logger.error(f"Failed to fetch policy {policy_id}: {e}")

        return None

    def _save_decision(self, decision: AutonomyDecision) -> None:
        """Save decision to storage."""
        if self.mode == AutonomyServiceMode.MOCK:
            self._mock_decisions.append(decision)
        elif self._decision_table:
            try:
                item = {
                    "decision_id": decision.decision_id,
                    "policy_id": decision.policy_id,
                    "organization_id": decision.organization_id,
                    "execution_id": decision.execution_id,
                    "severity": decision.severity,
                    "operation": decision.operation,
                    "repository": decision.repository,
                    "autonomy_level": decision.autonomy_level.value,
                    "hitl_required": decision.hitl_required,
                    "hitl_bypassed": decision.hitl_bypassed,
                    "auto_approved": decision.auto_approved,
                    "timestamp": decision.timestamp,
                    "metadata": decision.metadata,
                    "ttl": int(time.time()) + (self.DECISION_TTL_DAYS * 86400),
                }
                self._decision_table.put_item(Item=item)
            except Exception as e:
                logger.error(f"Failed to save decision {decision.decision_id}: {e}")

    def _decision_from_dict(self, data: dict[str, Any]) -> AutonomyDecision:
        """Create decision from DynamoDB item."""
        return AutonomyDecision(
            decision_id=data["decision_id"],
            policy_id=data["policy_id"],
            organization_id=data["organization_id"],
            execution_id=data["execution_id"],
            severity=data["severity"],
            operation=data["operation"],
            repository=data["repository"],
            autonomy_level=AutonomyLevel(data["autonomy_level"]),
            hitl_required=data["hitl_required"],
            hitl_bypassed=data["hitl_bypassed"],
            auto_approved=data["auto_approved"],
            timestamp=data["timestamp"],
            metadata=data.get("metadata", {}),
        )

    def _log_audit(
        self,
        policy_id: str,
        organization_id: str,
        change_type: PolicyChangeType,
        changed_by: str | None = None,
        previous_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        """Log audit entry."""
        entry = PolicyAuditEntry(
            audit_id=f"audit-{uuid.uuid4().hex[:12]}",
            policy_id=policy_id,
            organization_id=organization_id,
            change_type=change_type,
            changed_by=changed_by,
            changed_at=datetime.now().isoformat(),
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
        )

        if self.mode == AutonomyServiceMode.MOCK:
            self._mock_audit.append(entry)
        elif self._audit_table:
            try:
                item = {
                    "audit_id": entry.audit_id,
                    "policy_id": entry.policy_id,
                    "organization_id": entry.organization_id,
                    "change_type": entry.change_type.value,
                    "changed_by": entry.changed_by,
                    "changed_at": entry.changed_at,
                    "previous_value": (
                        json.dumps(entry.previous_value)
                        if entry.previous_value
                        else None
                    ),
                    "new_value": (
                        json.dumps(entry.new_value) if entry.new_value else None
                    ),
                    "reason": entry.reason,
                    "ttl": int(time.time()) + (self.AUDIT_TTL_DAYS * 86400),
                }
                self._audit_table.put_item(Item=item)
            except Exception as e:
                logger.error(f"Failed to save audit entry: {e}")

    def _get_from_cache(self, policy_id: str) -> AutonomyPolicy | None:
        """Get policy from cache if not expired."""
        if policy_id in self._policy_cache:
            policy, cached_at = self._policy_cache[policy_id]
            if time.time() - cached_at < self.CACHE_TTL_SECONDS:
                return policy
            else:
                del self._policy_cache[policy_id]
        return None

    def _add_to_cache(self, policy: AutonomyPolicy) -> None:
        """Add policy to cache."""
        self._policy_cache[policy.policy_id] = (policy, time.time())

    def _invalidate_cache(self, policy_id: str) -> None:
        """Invalidate cache entry."""
        self._policy_cache.pop(policy_id, None)


# =============================================================================
# Factory Functions
# =============================================================================


def create_autonomy_policy_service(
    mode: AutonomyServiceMode = AutonomyServiceMode.MOCK,
    region: str | None = None,
) -> AutonomyPolicyService:
    """
    Create an AutonomyPolicyService instance.

    Args:
        mode: Operating mode (MOCK or AWS)
        region: AWS region

    Returns:
        Configured AutonomyPolicyService instance
    """
    return AutonomyPolicyService(mode=mode, region=region)


# =============================================================================
# Demo / Test
# =============================================================================


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Project Aura - Autonomy Policy Service Demo")
    print("=" * 60)

    # Create service in mock mode
    service = create_autonomy_policy_service(mode=AutonomyServiceMode.MOCK)

    # Create policies from presets
    print("\n--- Creating Policies from Presets ---")

    defense_policy = service.create_policy_from_preset(
        organization_id="defense-org",
        preset_name="defense_contractor",
        created_by="admin@defense.gov",
    )
    print(f"Created: {defense_policy.name} (HITL: {defense_policy.hitl_enabled})")

    fintech_policy = service.create_policy_from_preset(
        organization_id="fintech-org",
        preset_name="fintech_startup",
        created_by="admin@fintech.io",
    )
    print(f"Created: {fintech_policy.name} (HITL: {fintech_policy.hitl_enabled})")

    autonomous_policy = service.create_policy_from_preset(
        organization_id="dev-org",
        preset_name="fully_autonomous",
        created_by="admin@dev.io",
    )
    print(f"Created: {autonomous_policy.name} (HITL: {autonomous_policy.hitl_enabled})")

    # Test HITL requirements
    print("\n--- Testing HITL Requirements ---")

    test_cases = [
        ("defense_contractor", defense_policy.policy_id, "CRITICAL", "security_patch"),
        ("defense_contractor", defense_policy.policy_id, "LOW", "security_patch"),
        ("fintech_startup", fintech_policy.policy_id, "HIGH", "security_patch"),
        ("fintech_startup", fintech_policy.policy_id, "LOW", "security_patch"),
        ("fully_autonomous", autonomous_policy.policy_id, "CRITICAL", "security_patch"),
        (
            "fully_autonomous",
            autonomous_policy.policy_id,
            "HIGH",
            "production_deployment",
        ),  # Guardrail
    ]

    for preset, policy_id, severity, operation in test_cases:
        requires_hitl = service.requires_hitl_approval(
            policy_id=policy_id,
            severity=severity,
            operation=operation,
        )
        print(f"  [{preset}] {severity}/{operation}: HITL={requires_hitl}")

    # Test toggling HITL
    print("\n--- Testing HITL Toggle ---")

    print(f"Before: {fintech_policy.name} HITL = {fintech_policy.hitl_enabled}")

    service.toggle_hitl(
        policy_id=fintech_policy.policy_id,
        hitl_enabled=False,
        updated_by="admin@fintech.io",
        reason="Enabling autonomous mode for dev environment",
    )

    updated_policy = service.get_policy(fintech_policy.policy_id)
    if updated_policy:
        print(f"After: {updated_policy.name} HITL = {updated_policy.hitl_enabled}")

    # Show that guardrails still apply
    requires_hitl = service.requires_hitl_approval(
        policy_id=fintech_policy.policy_id,
        severity="LOW",
        operation="production_deployment",  # Guardrail
    )
    print(f"Guardrail (production_deployment) still requires HITL: {requires_hitl}")

    # List presets
    print("\n--- Available Presets ---")
    presets_list: list[dict[str, Any]] = service.get_available_presets()
    preset_info: dict[str, Any]
    for preset_info in presets_list:
        preset_name = str(preset_info["name"])
        preset_desc = str(preset_info["description"])
        print(f"  {preset_name}: {preset_desc}")

    print("\n" + "=" * 60)
    print("Demo complete!")
