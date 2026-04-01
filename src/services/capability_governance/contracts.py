"""
Project Aura - Agent Capability Governance Contracts

Core data contracts, enums, and dataclasses for the capability governance framework.
Implements ADR-066 for per-agent tool access control.

Security Rationale:
- Strongly typed contracts prevent misconfiguration
- Immutable dataclasses ensure audit trail integrity
- Enum-based decisions enable exhaustive handling

Author: Project Aura Team
Created: 2026-01-26
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class CapabilityDecision(Enum):
    """
    Decision from capability check.

    Determines how the capability enforcement middleware handles a tool invocation.
    """

    ALLOW = "allow"  # Proceed with tool invocation
    DENY = "deny"  # Block invocation with error
    ESCALATE = "escalate"  # Requires HITL approval before proceeding
    AUDIT_ONLY = "audit_only"  # Allow but flag for review


class ToolClassification(Enum):
    """
    Risk classification for tools.

    Tools are classified by their potential impact on security and operations.
    Classification determines default access policy and audit requirements.
    """

    SAFE = "safe"  # Level 1: Always allowed, sample audit (10%)
    MONITORING = "monitoring"  # Level 2: Allowed, full audit
    DANGEROUS = "dangerous"  # Level 3: Explicit grant required
    CRITICAL = "critical"  # Level 4: HITL required always


class CapabilityScope(Enum):
    """
    Scope for dynamic capability grants.

    Defines how long and to what extent a dynamic grant applies.
    """

    SINGLE_USE = "single_use"  # One invocation only
    SESSION = "session"  # Current agent session
    TASK_TREE = "task_tree"  # All agents in execution tree
    TIME_BOUNDED = "time_bounded"  # Valid for specific duration


class ExecutionContext(Enum):
    """
    Execution context for capability evaluation.

    Context affects which capabilities are available and how they are audited.
    """

    TEST = "test"  # Unit/integration test environment
    SANDBOX = "sandbox"  # Isolated sandbox environment
    DEVELOPMENT = "development"  # Development environment
    STAGING = "staging"  # Pre-production staging
    PRODUCTION = "production"  # Production environment


class ActionType(Enum):
    """
    Action types for tool invocations.

    Defines the type of operation being performed on a tool.
    """

    READ = "read"  # Read-only access
    WRITE = "write"  # Modify data/state
    EXECUTE = "execute"  # Execute operations
    ADMIN = "admin"  # Administrative operations
    DELETE = "delete"  # Delete/destroy operations


@dataclass(frozen=True)
class ToolCapability:
    """
    Capability definition for a tool.

    Defines the security profile and access requirements for a specific tool.
    """

    tool_name: str
    classification: ToolClassification
    description: str = ""
    allowed_actions: tuple[str, ...] = ("read", "execute")
    requires_context: tuple[
        str, ...
    ] = ()  # Required contexts (e.g., "sandbox", "test")
    blocked_contexts: tuple[str, ...] = ()  # Blocked contexts (e.g., "production")
    rate_limit_per_minute: int = 60
    max_concurrent: int = 5
    requires_justification: bool = False
    audit_sample_rate: float = 1.0  # 1.0 = 100% audit

    def is_allowed_in_context(self, context: str) -> bool:
        """Check if tool is allowed in the given context."""
        if context in self.blocked_contexts:
            return False
        if self.requires_context and context not in self.requires_context:
            return False
        return True

    def is_action_allowed(self, action: str) -> bool:
        """Check if action is allowed for this tool."""
        return action in self.allowed_actions or "*" in self.allowed_actions


@dataclass
class CapabilityCheckResult:
    """
    Result of a capability check.

    Contains the decision and all metadata needed for audit and debugging.
    """

    decision: CapabilityDecision
    tool_name: str
    agent_id: str
    agent_type: str
    action: str
    context: str
    reason: str
    policy_version: str
    capability_source: str  # "base", "override", "dynamic_grant", "parent_inherited"
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_hash: str = ""
    parent_agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    processing_time_ms: float = 0.0

    @property
    def is_allowed(self) -> bool:
        """Check if the decision allows tool invocation."""
        return self.decision in (
            CapabilityDecision.ALLOW,
            CapabilityDecision.AUDIT_ONLY,
        )

    @property
    def requires_hitl(self) -> bool:
        """Check if HITL approval is required."""
        return self.decision == CapabilityDecision.ESCALATE

    def to_audit_record(self) -> dict[str, Any]:
        """Convert to audit-friendly format for DynamoDB."""
        return {
            "decision": self.decision.value,
            "tool_name": self.tool_name,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "action": self.action,
            "context": self.context,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "capability_source": self.capability_source,
            "checked_at": self.checked_at.isoformat(),
            "request_hash": self.request_hash,
            "parent_agent_id": self.parent_agent_id,
            "execution_id": self.execution_id,
            "processing_time_ms": self.processing_time_ms,
        }


@dataclass
class CapabilityContext:
    """
    Context for capability evaluation.

    Contains all information needed to evaluate whether an agent can invoke a tool.
    """

    agent_id: str
    agent_type: str
    tool_name: str
    action: str
    execution_context: str  # test, sandbox, development, production
    parent_agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    session_id: Optional[str] = None
    task_description: Optional[str] = None
    justification: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "tool_name": self.tool_name,
            "action": self.action,
            "execution_context": self.execution_context,
            "parent_agent_id": self.parent_agent_id,
            "execution_id": self.execution_id,
            "session_id": self.session_id,
            "task_description": self.task_description,
            "justification": self.justification,
        }


@dataclass
class CapabilityEscalationRequest:
    """
    Request for HITL capability escalation.

    Created when an agent needs a capability it doesn't have by default.
    """

    request_id: str
    agent_id: str
    agent_type: str
    requested_tool: str
    requested_action: str
    context: str
    justification: str
    task_description: str
    parent_agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    status: str = "pending"  # pending, approved, denied, expired, cancelled
    priority: str = "normal"  # low, normal, high, critical

    @property
    def is_expired(self) -> bool:
        """Check if the request has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_pending(self) -> bool:
        """Check if the request is still pending."""
        return self.status == "pending" and not self.is_expired

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "requested_tool": self.requested_tool,
            "requested_action": self.requested_action,
            "context": self.context,
            "justification": self.justification,
            "task_description": self.task_description,
            "parent_agent_id": self.parent_agent_id,
            "execution_id": self.execution_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status,
            "priority": self.priority,
        }


@dataclass
class CapabilityApprovalResponse:
    """
    Response to capability escalation request.

    Contains the approval decision and any constraints on the granted capability.
    """

    request_id: str
    approved: bool
    approver_id: str
    scope: CapabilityScope
    constraints: dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None
    approved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "approved": self.approved,
            "approver_id": self.approver_id,
            "scope": self.scope.value,
            "constraints": self.constraints,
            "reason": self.reason,
            "approved_at": self.approved_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class DynamicCapabilityGrant:
    """
    A dynamically granted capability.

    Represents a temporary or conditional grant of capability to an agent,
    typically issued through HITL approval.
    """

    grant_id: str
    agent_id: str
    tool_name: str
    action: str
    scope: CapabilityScope
    constraints: dict[str, Any]
    granted_by: str  # escalation request ID or admin action
    approver: str
    granted_at: datetime
    expires_at: datetime
    usage_count: int = 0
    max_usage: Optional[int] = None
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    context_restrictions: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if the grant is currently valid."""
        if self.revoked:
            return False
        if datetime.now(timezone.utc) > self.expires_at:
            return False
        if self.max_usage is not None and self.usage_count >= self.max_usage:
            return False
        return True

    @property
    def remaining_uses(self) -> Optional[int]:
        """Get remaining uses if max_usage is set."""
        if self.max_usage is None:
            return None
        return max(0, self.max_usage - self.usage_count)

    def is_applicable(self, tool: str, action: str, context: str) -> bool:
        """Check if this grant applies to the given invocation."""
        if not self.is_valid:
            return False
        if self.tool_name != tool:
            return False
        if self.action != action and self.action != "*":
            return False
        if self.context_restrictions and context not in self.context_restrictions:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "grant_id": self.grant_id,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "action": self.action,
            "scope": self.scope.value,
            "constraints": self.constraints,
            "granted_by": self.granted_by,
            "approver": self.approver,
            "granted_at": self.granted_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "usage_count": self.usage_count,
            "max_usage": self.max_usage,
            "revoked": self.revoked,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoked_reason": self.revoked_reason,
            "context_restrictions": self.context_restrictions,
        }


@dataclass
class CapabilityViolation:
    """
    Record of a capability violation.

    Created when an agent attempts to invoke a tool without proper authorization.
    """

    violation_id: str
    agent_id: str
    agent_type: str
    tool_name: str
    action: str
    context: str
    decision: CapabilityDecision
    reason: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    parent_agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    severity: str = "medium"  # low, medium, high, critical
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "violation_id": self.violation_id,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "tool_name": self.tool_name,
            "action": self.action,
            "context": self.context,
            "decision": self.decision.value,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
            "parent_agent_id": self.parent_agent_id,
            "execution_id": self.execution_id,
            "severity": self.severity,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": (
                self.acknowledged_at.isoformat() if self.acknowledged_at else None
            ),
        }


# Type aliases for clarity
AgentType = str
ToolName = str
PolicyVersion = str
GrantId = str
RequestId = str
