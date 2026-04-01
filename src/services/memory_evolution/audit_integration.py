"""
Project Aura - Audit Integration for Memory Evolution (ADR-080)

Integrates memory evolution operations with the NeuralMemoryAuditLogger
for compliance-ready audit trails.

Audit Events:
- REFINE_OPERATION: Refine action executed
- EVOLUTION_TRACKING: Task completion recorded
- SECURITY_BOUNDARY: Security boundary check
- CIRCUIT_BREAKER: Circuit breaker state change

Reference: ADR-080 Evo-Memory Enhancements (Phase 2)
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol

from .config import MemoryEvolutionConfig, get_memory_evolution_config
from .contracts import RefineAction, RefineOperation, RefineResult

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================


class EvolutionAuditEventType(Enum):
    """Types of auditable memory evolution events."""

    REFINE_OPERATION = "refine_operation"
    EVOLUTION_TRACKING = "evolution_tracking"
    SECURITY_BOUNDARY = "security_boundary"
    CIRCUIT_BREAKER = "circuit_breaker"
    CONFIG_CHANGE = "config_change"
    ROLLBACK = "rollback"


class AuditSeverity(Enum):
    """Severity levels for audit events."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# =============================================================================
# PROTOCOLS
# =============================================================================


class NeuralMemoryAuditLoggerProtocol(Protocol):
    """Protocol for NeuralMemoryAuditLogger operations."""

    def log_event(
        self,
        event_type: str,
        severity: str,
        operation: str,
        actor: str,
        resource: str,
        details: dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> str:
        """Log an audit event. Returns event_id."""
        ...


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class EvolutionAuditRecord:
    """Structured audit record for memory evolution operations.

    Designed for compliance with CMMC Level 3, SOX, NIST requirements.
    """

    event_id: str
    timestamp: str
    event_type: EvolutionAuditEventType
    severity: AuditSeverity
    operation: str
    actor: str  # agent_id
    tenant_id: str
    security_domain: str
    resource: str  # memory IDs, action IDs
    details: dict[str, Any]
    outcome: str  # "success", "failure", "blocked"
    latency_ms: float
    correlation_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "operation": self.operation,
            "actor": self.actor,
            "tenant_id": self.tenant_id,
            "security_domain": self.security_domain,
            "resource": self.resource,
            "details": self.details,
            "outcome": self.outcome,
            "latency_ms": self.latency_ms,
            "correlation_id": self.correlation_id,
        }


# =============================================================================
# AUDIT ADAPTER
# =============================================================================


class EvolutionAuditAdapter:
    """Adapts memory evolution events to NeuralMemoryAuditLogger format.

    Provides structured audit logging for:
    - Refine operations (CONSOLIDATE, PRUNE, REINFORCE, etc.)
    - Security boundary validations
    - Circuit breaker state changes
    - Configuration changes

    Thread Safety:
    - All methods are stateless and can be called concurrently
    - Delegates actual logging to NeuralMemoryAuditLogger
    """

    SERVICE_NAME = "MemoryEvolutionService"

    def __init__(
        self,
        audit_logger: NeuralMemoryAuditLoggerProtocol,
        config: Optional[MemoryEvolutionConfig] = None,
    ):
        """
        Initialize audit adapter.

        Args:
            audit_logger: The NeuralMemoryAuditLogger to delegate to
            config: Memory evolution configuration
        """
        self.audit_logger = audit_logger
        self.config = config or get_memory_evolution_config()

    def log_refine_operation(
        self,
        action: RefineAction,
        result: RefineResult,
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        Log a completed refine operation.

        Args:
            action: The refine action that was executed
            result: The result of the operation
            correlation_id: Optional correlation ID for tracing

        Returns:
            Event ID from the audit logger
        """
        severity = AuditSeverity.INFO if result.success else AuditSeverity.WARNING

        details = {
            "operation": action.operation.value,
            "target_memory_ids": action.target_memory_ids,
            "confidence": action.confidence,
            "reasoning": action.reasoning,
            "success": result.success,
            "affected_memory_ids": result.affected_memory_ids,
            "rollback_token": result.rollback_token,
            "latency_ms": result.latency_ms,
            "metrics": result.metrics,
        }

        if result.error:
            details["error"] = result.error

        return self.audit_logger.log_event(
            event_type=EvolutionAuditEventType.REFINE_OPERATION.value,
            severity=severity.value,
            operation=action.operation.value,
            actor=action.agent_id or "unknown",
            resource=",".join(action.target_memory_ids[:5]),  # Limit for readability
            details=details,
            correlation_id=correlation_id,
        )

    def log_security_boundary_check(
        self,
        agent_id: str,
        tenant_id: str,
        security_domain: str,
        memory_ids: list[str],
        allowed: bool,
        reason: str,
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        Log a security boundary validation.

        Args:
            agent_id: Agent requesting access
            tenant_id: Tenant identifier
            security_domain: Security domain being accessed
            memory_ids: Memory IDs involved
            allowed: Whether access was allowed
            reason: Reason for the decision
            correlation_id: Optional correlation ID

        Returns:
            Event ID from the audit logger
        """
        severity = AuditSeverity.INFO if allowed else AuditSeverity.WARNING

        details = {
            "tenant_id": tenant_id,
            "security_domain": security_domain,
            "memory_ids": memory_ids[:10],
            "allowed": allowed,
            "reason": reason,
        }

        return self.audit_logger.log_event(
            event_type=EvolutionAuditEventType.SECURITY_BOUNDARY.value,
            severity=severity.value,
            operation="security_check",
            actor=agent_id,
            resource=f"tenant:{tenant_id}/domain:{security_domain}",
            details=details,
            correlation_id=correlation_id,
        )

    def log_circuit_breaker_change(
        self,
        operation: RefineOperation,
        previous_state: str,
        new_state: str,
        failure_count: int,
        reason: str,
    ) -> str:
        """
        Log a circuit breaker state change.

        Args:
            operation: Operation the circuit breaker is for
            previous_state: Previous state (closed, open, half_open)
            new_state: New state
            failure_count: Number of failures triggering the change
            reason: Reason for the state change

        Returns:
            Event ID from the audit logger
        """
        # Circuit breaker opening is warning-worthy
        severity = AuditSeverity.WARNING if new_state == "open" else AuditSeverity.INFO

        details = {
            "operation": operation.value,
            "previous_state": previous_state,
            "new_state": new_state,
            "failure_count": failure_count,
            "reason": reason,
        }

        return self.audit_logger.log_event(
            event_type=EvolutionAuditEventType.CIRCUIT_BREAKER.value,
            severity=severity.value,
            operation="circuit_breaker_transition",
            actor="system",
            resource=f"circuit_breaker:{operation.value}",
            details=details,
        )

    def log_evolution_tracking(
        self,
        agent_id: str,
        task_id: str,
        tenant_id: str,
        refine_actions: list[RefineAction],
        outcome: str,
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        Log evolution tracking for a completed task.

        Args:
            agent_id: Agent that completed the task
            task_id: Task identifier
            tenant_id: Tenant identifier
            refine_actions: Refine actions that were executed
            outcome: Task outcome
            correlation_id: Optional correlation ID

        Returns:
            Event ID from the audit logger
        """
        action_summary = {}
        for action in refine_actions:
            op = action.operation.value
            action_summary[op] = action_summary.get(op, 0) + 1

        details = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "outcome": outcome,
            "refine_action_count": len(refine_actions),
            "refine_action_summary": action_summary,
        }

        return self.audit_logger.log_event(
            event_type=EvolutionAuditEventType.EVOLUTION_TRACKING.value,
            severity=AuditSeverity.INFO.value,
            operation="task_completion",
            actor=agent_id,
            resource=f"task:{task_id}",
            details=details,
            correlation_id=correlation_id,
        )

    def log_rollback(
        self,
        rollback_token: str,
        original_action: RefineAction,
        success: bool,
        restored_memory_ids: list[str],
        reason: str,
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        Log a rollback operation.

        Args:
            rollback_token: Token used for rollback
            original_action: The original action being rolled back
            success: Whether rollback succeeded
            restored_memory_ids: Memory IDs that were restored
            reason: Reason for rollback
            correlation_id: Optional correlation ID

        Returns:
            Event ID from the audit logger
        """
        severity = AuditSeverity.WARNING if success else AuditSeverity.ERROR

        details = {
            "rollback_token": rollback_token,
            "original_operation": original_action.operation.value,
            "original_target_ids": original_action.target_memory_ids,
            "success": success,
            "restored_memory_ids": restored_memory_ids,
            "reason": reason,
        }

        return self.audit_logger.log_event(
            event_type=EvolutionAuditEventType.ROLLBACK.value,
            severity=severity.value,
            operation="rollback",
            actor=original_action.agent_id or "system",
            resource=f"rollback:{rollback_token}",
            details=details,
            correlation_id=correlation_id,
        )


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_adapter_instance: Optional[EvolutionAuditAdapter] = None


def get_evolution_audit_adapter(
    audit_logger: Optional[NeuralMemoryAuditLoggerProtocol] = None,
    config: Optional[MemoryEvolutionConfig] = None,
) -> EvolutionAuditAdapter:
    """Get or create the singleton EvolutionAuditAdapter instance."""
    global _adapter_instance
    if _adapter_instance is None:
        if audit_logger is None:
            raise ValueError("audit_logger is required for initial creation")
        _adapter_instance = EvolutionAuditAdapter(
            audit_logger=audit_logger,
            config=config,
        )
    return _adapter_instance


def reset_evolution_audit_adapter() -> None:
    """Reset the singleton instance (for testing)."""
    global _adapter_instance
    _adapter_instance = None
