"""
Project Aura - Multi-Agent Memory Sharing (ADR-080 Phase 6)

Implements cross-agent strategy propagation and approval workflows
for sharing successful strategies between agents.

Components:
- CrossAgentPropagator: Broadcasts approved strategies to eligible agents
- StrategyPromotionService: Manages approval workflow for shared strategies
- SharingPolicy: Configurable policies for strategy sharing

Workflow:
1. Agent discovers successful strategy (via ABSTRACT operation)
2. Strategy nominated for sharing based on success metrics
3. Approval workflow triggered (HITL or auto-approve based on confidence)
4. Approved strategies propagated to eligible agents
5. Receiving agents can accept/reject based on relevance

Security:
- Strategies only shared within same tenant
- Security domain boundaries enforced
- Audit trail for all sharing operations
- Rate limiting to prevent spam

Compliance:
- ADR-080: Evo-Memory Enhancements (Phase 6)
- CMMC Level 3: Multi-tenant isolation
- NIST 800-53: AC-4 (Information Flow Enforcement)
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol

from .contracts import AbstractedStrategy, AgentId, SecurityDomain, TenantId
from .exceptions import (
    SecurityBoundaryViolation,
    TenantIsolationViolation,
    ValidationError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================


class SharingStatus(Enum):
    """Status of a strategy sharing request."""

    PENDING = "pending"  # Awaiting approval
    APPROVED = "approved"  # Approved for sharing
    REJECTED = "rejected"  # Rejected by approver
    PROPAGATING = "propagating"  # Being broadcast to agents
    COMPLETED = "completed"  # Successfully shared
    FAILED = "failed"  # Sharing failed
    EXPIRED = "expired"  # Request expired before approval


class ApprovalType(Enum):
    """Type of approval required for strategy sharing."""

    AUTO = "auto"  # Automatic approval based on confidence
    HUMAN = "human"  # Requires human approval
    PEER = "peer"  # Peer agent approval
    ADMIN = "admin"  # Admin/supervisor approval


class PropagationScope(Enum):
    """Scope of strategy propagation."""

    SAME_AGENT_TYPE = "same_agent_type"  # Only to agents of same type
    SAME_DOMAIN = "same_domain"  # Only within same security domain
    SAME_TENANT = "same_tenant"  # All agents in tenant
    GLOBAL = "global"  # All eligible agents (cross-tenant, admin only)


class AcceptanceDecision(Enum):
    """Decision by receiving agent on shared strategy."""

    ACCEPTED = "accepted"  # Strategy accepted and integrated
    REJECTED = "rejected"  # Strategy rejected as irrelevant
    DEFERRED = "deferred"  # Decision deferred for later
    FILTERED = "filtered"  # Automatically filtered by policy


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class SharingPolicy:
    """Policy governing strategy sharing behavior."""

    auto_approve_threshold: float = 0.9  # Confidence for auto-approval
    min_success_rate: float = 0.8  # Min success rate for nomination
    min_usage_count: int = 5  # Min times used before sharing
    max_propagation_batch: int = 50  # Max agents per propagation batch
    propagation_timeout_seconds: int = 300  # Timeout for propagation
    require_peer_approval: bool = False  # Require peer agent approval
    allow_cross_domain: bool = False  # Allow cross-domain sharing
    rate_limit_per_hour: int = 10  # Max sharing requests per hour per agent

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "auto_approve_threshold": self.auto_approve_threshold,
            "min_success_rate": self.min_success_rate,
            "min_usage_count": self.min_usage_count,
            "max_propagation_batch": self.max_propagation_batch,
            "propagation_timeout_seconds": self.propagation_timeout_seconds,
            "require_peer_approval": self.require_peer_approval,
            "allow_cross_domain": self.allow_cross_domain,
            "rate_limit_per_hour": self.rate_limit_per_hour,
        }


@dataclass
class SharingRequest:
    """Request to share a strategy with other agents."""

    request_id: str
    strategy_id: str
    source_agent_id: AgentId
    tenant_id: TenantId
    security_domain: SecurityDomain
    scope: PropagationScope
    status: SharingStatus = SharingStatus.PENDING
    approval_type: ApprovalType = ApprovalType.AUTO
    confidence: float = 0.0
    success_rate: float = 0.0
    usage_count: int = 0
    target_agent_ids: list[AgentId] = field(default_factory=list)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate request after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        if not 0.0 <= self.success_rate <= 1.0:
            raise ValueError(
                f"Success rate must be between 0.0 and 1.0, got {self.success_rate}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "request_id": self.request_id,
            "strategy_id": self.strategy_id,
            "source_agent_id": self.source_agent_id,
            "tenant_id": self.tenant_id,
            "security_domain": self.security_domain,
            "scope": self.scope.value,
            "status": self.status.value,
            "approval_type": self.approval_type.value,
            "confidence": self.confidence,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "target_agent_ids": self.target_agent_ids,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }


@dataclass
class PropagationResult:
    """Result of strategy propagation to agents."""

    request_id: str
    strategy_id: str
    agents_targeted: int
    agents_received: int
    agents_accepted: int
    agents_rejected: int
    agents_failed: int
    failed_agent_ids: list[AgentId] = field(default_factory=list)
    propagated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def success_rate(self) -> float:
        """Calculate propagation success rate."""
        if self.agents_targeted == 0:
            return 0.0
        return self.agents_received / self.agents_targeted

    @property
    def acceptance_rate(self) -> float:
        """Calculate acceptance rate among received agents."""
        if self.agents_received == 0:
            return 0.0
        return self.agents_accepted / self.agents_received

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "request_id": self.request_id,
            "strategy_id": self.strategy_id,
            "agents_targeted": self.agents_targeted,
            "agents_received": self.agents_received,
            "agents_accepted": self.agents_accepted,
            "agents_rejected": self.agents_rejected,
            "agents_failed": self.agents_failed,
            "failed_agent_ids": self.failed_agent_ids,
            "success_rate": self.success_rate,
            "acceptance_rate": self.acceptance_rate,
            "propagated_at": self.propagated_at.isoformat(),
        }


@dataclass
class AgentAcceptance:
    """Record of an agent's acceptance decision on a shared strategy."""

    agent_id: AgentId
    strategy_id: str
    request_id: str
    decision: AcceptanceDecision
    relevance_score: float = 0.0  # How relevant the strategy is to this agent
    reasoning: Optional[str] = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "strategy_id": self.strategy_id,
            "request_id": self.request_id,
            "decision": self.decision.value,
            "relevance_score": self.relevance_score,
            "reasoning": self.reasoning,
            "decided_at": self.decided_at.isoformat(),
        }


# =============================================================================
# PROTOCOLS
# =============================================================================


class AgentRegistryProtocol(Protocol):
    """Protocol for agent registry operations."""

    async def get_agents_by_tenant(self, tenant_id: TenantId) -> list[dict[str, Any]]:
        """Get all agents for a tenant."""
        ...

    async def get_agents_by_domain(
        self, tenant_id: TenantId, security_domain: SecurityDomain
    ) -> list[dict[str, Any]]:
        """Get agents in a security domain."""
        ...

    async def get_agents_by_type(
        self, tenant_id: TenantId, agent_type: str
    ) -> list[dict[str, Any]]:
        """Get agents of a specific type."""
        ...

    async def get_agent(self, agent_id: AgentId) -> Optional[dict[str, Any]]:
        """Get agent details."""
        ...


class StrategyStoreProtocol(Protocol):
    """Protocol for strategy storage operations."""

    async def get_strategy(
        self, strategy_id: str, tenant_id: TenantId
    ) -> Optional[AbstractedStrategy]:
        """Get a strategy by ID."""
        ...

    async def get_strategy_metrics(self, strategy_id: str) -> dict[str, Any]:
        """Get usage metrics for a strategy."""
        ...

    async def copy_strategy_to_agent(
        self, strategy: AbstractedStrategy, target_agent_id: AgentId
    ) -> str:
        """Copy strategy to target agent's memory. Returns new strategy ID."""
        ...


class SharingRequestStoreProtocol(Protocol):
    """Protocol for sharing request storage."""

    async def save_request(self, request: SharingRequest) -> None:
        """Save a sharing request."""
        ...

    async def get_request(self, request_id: str) -> Optional[SharingRequest]:
        """Get a sharing request by ID."""
        ...

    async def update_request(
        self, request_id: str, updates: dict[str, Any]
    ) -> SharingRequest:
        """Update a sharing request."""
        ...

    async def get_pending_requests(self, tenant_id: TenantId) -> list[SharingRequest]:
        """Get all pending requests for a tenant."""
        ...

    async def count_requests_since(self, agent_id: AgentId, since: datetime) -> int:
        """Count requests from an agent since a timestamp."""
        ...


class NotificationServiceProtocol(Protocol):
    """Protocol for notification delivery."""

    async def notify_approval_required(
        self, request: SharingRequest, approvers: list[str]
    ) -> None:
        """Notify approvers of pending request."""
        ...

    async def notify_strategy_shared(
        self, agent_id: AgentId, strategy: AbstractedStrategy
    ) -> None:
        """Notify agent of shared strategy."""
        ...


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class MultiAgentSharingConfig:
    """Configuration for multi-agent sharing service."""

    default_policy: SharingPolicy = field(default_factory=SharingPolicy)
    enable_auto_approval: bool = True
    enable_peer_approval: bool = False
    request_expiry_hours: int = 24
    max_pending_requests: int = 100
    propagation_batch_size: int = 10
    enable_relevance_filtering: bool = True
    relevance_threshold: float = 0.5  # Min relevance for auto-acceptance

    @classmethod
    def from_environment(cls) -> "MultiAgentSharingConfig":
        """Create config from environment variables."""
        import os

        return cls(
            enable_auto_approval=os.getenv(
                "ADR080_ENABLE_AUTO_APPROVAL", "true"
            ).lower()
            == "true",
            enable_peer_approval=os.getenv(
                "ADR080_ENABLE_PEER_APPROVAL", "false"
            ).lower()
            == "true",
            request_expiry_hours=int(os.getenv("ADR080_REQUEST_EXPIRY_HOURS", "24")),
            max_pending_requests=int(os.getenv("ADR080_MAX_PENDING_REQUESTS", "100")),
            propagation_batch_size=int(
                os.getenv("ADR080_PROPAGATION_BATCH_SIZE", "10")
            ),
            enable_relevance_filtering=os.getenv(
                "ADR080_ENABLE_RELEVANCE_FILTERING", "true"
            ).lower()
            == "true",
            relevance_threshold=float(os.getenv("ADR080_RELEVANCE_THRESHOLD", "0.5")),
        )


# =============================================================================
# STRATEGY PROMOTION SERVICE
# =============================================================================


class StrategyPromotionService:
    """
    Manages the approval workflow for sharing strategies between agents.

    Handles nomination, approval routing, and status tracking for
    strategy sharing requests.
    """

    def __init__(
        self,
        request_store: SharingRequestStoreProtocol,
        strategy_store: StrategyStoreProtocol,
        notification_service: Optional[NotificationServiceProtocol] = None,
        config: Optional[MultiAgentSharingConfig] = None,
    ):
        """Initialize the promotion service."""
        self.request_store = request_store
        self.strategy_store = strategy_store
        self.notification_service = notification_service
        self.config = config or MultiAgentSharingConfig()

    async def nominate_for_sharing(
        self,
        strategy_id: str,
        source_agent_id: AgentId,
        tenant_id: TenantId,
        security_domain: SecurityDomain,
        scope: PropagationScope = PropagationScope.SAME_DOMAIN,
        target_agent_ids: Optional[list[AgentId]] = None,
    ) -> SharingRequest:
        """
        Nominate a strategy for sharing with other agents.

        Args:
            strategy_id: ID of strategy to share
            source_agent_id: Agent nominating the strategy
            tenant_id: Tenant for isolation
            security_domain: Security domain boundary
            scope: Propagation scope
            target_agent_ids: Optional specific agents to target

        Returns:
            SharingRequest with pending status
        """
        # Check rate limit
        one_hour_ago = datetime.now(timezone.utc) - __import__("datetime").timedelta(
            hours=1
        )
        recent_count = await self.request_store.count_requests_since(
            source_agent_id, one_hour_ago
        )
        if recent_count >= self.config.default_policy.rate_limit_per_hour:
            raise ValidationError(
                f"Rate limit exceeded: {recent_count} requests in last hour"
            )

        # Get strategy and validate
        strategy = await self.strategy_store.get_strategy(strategy_id, tenant_id)
        if not strategy:
            raise ValidationError(f"Strategy not found: {strategy_id}")

        # Validate tenant isolation
        if strategy.tenant_id != tenant_id:
            raise TenantIsolationViolation(
                "Cannot share strategy from different tenant"
            )

        # Validate security domain for non-global scope
        if scope != PropagationScope.GLOBAL:
            if not self.config.default_policy.allow_cross_domain:
                if strategy.security_domain != security_domain:
                    raise SecurityBoundaryViolation(
                        "Cross-domain sharing not allowed by policy"
                    )

        # Get strategy metrics
        metrics = await self.strategy_store.get_strategy_metrics(strategy_id)
        success_rate = metrics.get("success_rate", 0.0)
        usage_count = metrics.get("usage_count", 0)

        # Check minimum requirements
        policy = self.config.default_policy
        if success_rate < policy.min_success_rate:
            raise ValidationError(
                f"Strategy success rate {success_rate:.2%} below minimum "
                f"{policy.min_success_rate:.2%}"
            )
        if usage_count < policy.min_usage_count:
            raise ValidationError(
                f"Strategy usage count {usage_count} below minimum "
                f"{policy.min_usage_count}"
            )

        # Determine approval type
        confidence = strategy.confidence
        if (
            self.config.enable_auto_approval
            and confidence >= policy.auto_approve_threshold
        ):
            approval_type = ApprovalType.AUTO
        elif self.config.enable_peer_approval or policy.require_peer_approval:
            approval_type = ApprovalType.PEER
        else:
            approval_type = ApprovalType.HUMAN

        # Create request
        request = SharingRequest(
            request_id=f"share-{uuid.uuid4().hex[:16]}",
            strategy_id=strategy_id,
            source_agent_id=source_agent_id,
            tenant_id=tenant_id,
            security_domain=security_domain,
            scope=scope,
            approval_type=approval_type,
            confidence=confidence,
            success_rate=success_rate,
            usage_count=usage_count,
            target_agent_ids=target_agent_ids or [],
            expires_at=datetime.now(timezone.utc)
            + __import__("datetime").timedelta(hours=self.config.request_expiry_hours),
        )

        # Auto-approve if eligible
        if approval_type == ApprovalType.AUTO:
            request.status = SharingStatus.APPROVED
            request.approved_by = "auto"
            request.approved_at = datetime.now(timezone.utc)
            logger.info(
                "Auto-approved sharing request %s (confidence: %.2f)",
                request.request_id,
                confidence,
            )
        else:
            # Notify approvers
            if self.notification_service:
                approvers = await self._get_approvers(request)
                await self.notification_service.notify_approval_required(
                    request, approvers
                )

        await self.request_store.save_request(request)

        logger.info(
            "Created sharing request %s for strategy %s (status: %s)",
            request.request_id,
            strategy_id,
            request.status.value,
        )

        return request

    async def approve_request(
        self,
        request_id: str,
        approver_id: str,
        tenant_id: TenantId,
    ) -> SharingRequest:
        """
        Approve a sharing request.

        Args:
            request_id: Request to approve
            approver_id: ID of approver (human or peer agent)
            tenant_id: Tenant for validation

        Returns:
            Updated SharingRequest
        """
        request = await self.request_store.get_request(request_id)
        if not request:
            raise ValidationError(f"Request not found: {request_id}")

        if request.tenant_id != tenant_id:
            raise TenantIsolationViolation(
                "Cannot approve request from different tenant"
            )

        if request.status != SharingStatus.PENDING:
            raise ValidationError(
                f"Cannot approve request in status: {request.status.value}"
            )

        # Check expiration
        if request.expires_at and datetime.now(timezone.utc) > request.expires_at:
            await self.request_store.update_request(
                request_id, {"status": SharingStatus.EXPIRED.value}
            )
            raise ValidationError("Request has expired")

        # Update request
        updated = await self.request_store.update_request(
            request_id,
            {
                "status": SharingStatus.APPROVED.value,
                "approved_by": approver_id,
                "approved_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info("Approved sharing request %s by %s", request_id, approver_id)

        return updated

    async def reject_request(
        self,
        request_id: str,
        rejector_id: str,
        tenant_id: TenantId,
        reason: str,
    ) -> SharingRequest:
        """
        Reject a sharing request.

        Args:
            request_id: Request to reject
            rejector_id: ID of rejector
            tenant_id: Tenant for validation
            reason: Rejection reason

        Returns:
            Updated SharingRequest
        """
        request = await self.request_store.get_request(request_id)
        if not request:
            raise ValidationError(f"Request not found: {request_id}")

        if request.tenant_id != tenant_id:
            raise TenantIsolationViolation(
                "Cannot reject request from different tenant"
            )

        if request.status != SharingStatus.PENDING:
            raise ValidationError(
                f"Cannot reject request in status: {request.status.value}"
            )

        updated = await self.request_store.update_request(
            request_id,
            {
                "status": SharingStatus.REJECTED.value,
                "approved_by": rejector_id,
                "rejection_reason": reason,
            },
        )

        logger.info(
            "Rejected sharing request %s by %s: %s",
            request_id,
            rejector_id,
            reason,
        )

        return updated

    async def get_pending_requests(self, tenant_id: TenantId) -> list[SharingRequest]:
        """Get all pending requests for a tenant."""
        requests = await self.request_store.get_pending_requests(tenant_id)

        # Filter out expired
        now = datetime.now(timezone.utc)
        valid_requests = []
        for req in requests:
            if req.expires_at and now > req.expires_at:
                await self.request_store.update_request(
                    req.request_id, {"status": SharingStatus.EXPIRED.value}
                )
            else:
                valid_requests.append(req)

        return valid_requests

    async def _get_approvers(self, request: SharingRequest) -> list[str]:
        """Determine approvers for a request."""
        # For now, return empty list - actual implementation would
        # look up admin users or peer agents based on approval type
        return []


# =============================================================================
# CROSS-AGENT PROPAGATOR
# =============================================================================


class CrossAgentPropagator:
    """
    Broadcasts approved strategies to eligible agents.

    Handles the actual distribution of strategies to target agents,
    including relevance filtering and acceptance tracking.
    """

    def __init__(
        self,
        agent_registry: AgentRegistryProtocol,
        strategy_store: StrategyStoreProtocol,
        request_store: SharingRequestStoreProtocol,
        notification_service: Optional[NotificationServiceProtocol] = None,
        config: Optional[MultiAgentSharingConfig] = None,
    ):
        """Initialize the propagator."""
        self.agent_registry = agent_registry
        self.strategy_store = strategy_store
        self.request_store = request_store
        self.notification_service = notification_service
        self.config = config or MultiAgentSharingConfig()

    async def propagate(self, request_id: str) -> PropagationResult:
        """
        Propagate an approved strategy to target agents.

        Args:
            request_id: ID of approved sharing request

        Returns:
            PropagationResult with distribution metrics
        """
        request = await self.request_store.get_request(request_id)
        if not request:
            raise ValidationError(f"Request not found: {request_id}")

        if request.status != SharingStatus.APPROVED:
            raise ValidationError(
                f"Cannot propagate request in status: {request.status.value}"
            )

        # Update status to propagating
        await self.request_store.update_request(
            request_id, {"status": SharingStatus.PROPAGATING.value}
        )

        try:
            # Get strategy
            strategy = await self.strategy_store.get_strategy(
                request.strategy_id, request.tenant_id
            )
            if not strategy:
                raise ValidationError(f"Strategy not found: {request.strategy_id}")

            # Get target agents
            target_agents = await self._get_target_agents(request, strategy)

            if not target_agents:
                logger.warning("No eligible agents found for propagation")
                await self.request_store.update_request(
                    request_id, {"status": SharingStatus.COMPLETED.value}
                )
                return PropagationResult(
                    request_id=request_id,
                    strategy_id=request.strategy_id,
                    agents_targeted=0,
                    agents_received=0,
                    agents_accepted=0,
                    agents_rejected=0,
                    agents_failed=0,
                )

            # Propagate to agents in batches
            result = await self._propagate_to_agents(strategy, target_agents, request)

            # Update request status
            final_status = (
                SharingStatus.COMPLETED
                if result.agents_failed == 0
                else SharingStatus.FAILED
            )
            await self.request_store.update_request(
                request_id,
                {
                    "status": final_status.value,
                    "metadata": {
                        **request.metadata,
                        "propagation_result": result.to_dict(),
                    },
                },
            )

            return result

        except Exception as e:
            logger.error("Propagation failed for request %s: %s", request_id, e)
            await self.request_store.update_request(
                request_id, {"status": SharingStatus.FAILED.value}
            )
            raise

    async def _get_target_agents(
        self,
        request: SharingRequest,
        strategy: AbstractedStrategy,
    ) -> list[dict[str, Any]]:
        """Get list of target agents based on scope."""
        # If specific targets provided, use those
        if request.target_agent_ids:
            agents = []
            for agent_id in request.target_agent_ids:
                agent = await self.agent_registry.get_agent(agent_id)
                if agent and agent.get("tenant_id") == request.tenant_id:
                    agents.append(agent)
            return agents

        # Otherwise, get by scope
        if request.scope == PropagationScope.SAME_DOMAIN:
            agents = await self.agent_registry.get_agents_by_domain(
                request.tenant_id, request.security_domain
            )
        elif request.scope == PropagationScope.SAME_TENANT:
            agents = await self.agent_registry.get_agents_by_tenant(request.tenant_id)
        elif request.scope == PropagationScope.SAME_AGENT_TYPE:
            # Get source agent to determine type
            source_agent = await self.agent_registry.get_agent(request.source_agent_id)
            if source_agent:
                agent_type = source_agent.get("agent_type", "unknown")
                agents = await self.agent_registry.get_agents_by_type(
                    request.tenant_id, agent_type
                )
            else:
                agents = []
        else:
            # GLOBAL scope - would require special permissions
            agents = []

        # Exclude source agent
        agents = [a for a in agents if a.get("agent_id") != request.source_agent_id]

        return agents

    async def _propagate_to_agents(
        self,
        strategy: AbstractedStrategy,
        target_agents: list[dict[str, Any]],
        request: SharingRequest,
    ) -> PropagationResult:
        """Propagate strategy to target agents."""
        agents_received = 0
        agents_accepted = 0
        agents_rejected = 0
        agents_failed = 0
        failed_ids: list[AgentId] = []

        batch_size = self.config.propagation_batch_size

        for i in range(0, len(target_agents), batch_size):
            batch = target_agents[i : i + batch_size]

            for agent in batch:
                agent_id = agent.get("agent_id")
                try:
                    # Check relevance if enabled
                    if self.config.enable_relevance_filtering:
                        relevance = await self._compute_relevance(strategy, agent)
                        if relevance < self.config.relevance_threshold:
                            agents_rejected += 1
                            logger.debug(
                                "Agent %s rejected strategy %s (relevance: %.2f)",
                                agent_id,
                                strategy.strategy_id,
                                relevance,
                            )
                            continue

                    # Copy strategy to agent
                    await self.strategy_store.copy_strategy_to_agent(strategy, agent_id)

                    # Notify agent
                    if self.notification_service:
                        await self.notification_service.notify_strategy_shared(
                            agent_id, strategy
                        )

                    agents_received += 1
                    agents_accepted += 1

                    logger.info(
                        "Propagated strategy %s to agent %s",
                        strategy.strategy_id,
                        agent_id,
                    )

                except Exception as e:
                    logger.error("Failed to propagate to agent %s: %s", agent_id, e)
                    agents_failed += 1
                    failed_ids.append(agent_id)

        return PropagationResult(
            request_id=request.request_id,
            strategy_id=strategy.strategy_id,
            agents_targeted=len(target_agents),
            agents_received=agents_received,
            agents_accepted=agents_accepted,
            agents_rejected=agents_rejected,
            agents_failed=agents_failed,
            failed_agent_ids=failed_ids,
        )

    async def _compute_relevance(
        self,
        strategy: AbstractedStrategy,
        agent: dict[str, Any],
    ) -> float:
        """
        Compute relevance score of strategy to agent.

        This is a simplified implementation - actual relevance
        could use embedding similarity, task history overlap, etc.
        """
        # Check if agent's domain matches strategy's applicable conditions
        agent_type = agent.get("agent_type", "")
        agent_domain = agent.get("domain", "")

        relevance = 0.3  # Base relevance - below default threshold

        # Boost if agent type mentioned in conditions
        # Note: Only check non-empty strings to avoid "" in "anything" == True
        for condition in strategy.applicability_conditions:
            if agent_type and agent_type.lower() in condition.lower():
                relevance += 0.4
            if agent_domain and agent_domain.lower() in condition.lower():
                relevance += 0.3

        return min(relevance, 1.0)

    async def record_acceptance(
        self,
        agent_id: AgentId,
        strategy_id: str,
        request_id: str,
        decision: AcceptanceDecision,
        relevance_score: float = 0.0,
        reasoning: Optional[str] = None,
    ) -> AgentAcceptance:
        """Record an agent's acceptance decision."""
        acceptance = AgentAcceptance(
            agent_id=agent_id,
            strategy_id=strategy_id,
            request_id=request_id,
            decision=decision,
            relevance_score=relevance_score,
            reasoning=reasoning,
        )

        logger.info(
            "Agent %s %s strategy %s",
            agent_id,
            decision.value,
            strategy_id,
        )

        return acceptance


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_promotion_service: Optional[StrategyPromotionService] = None
_propagator: Optional[CrossAgentPropagator] = None


def get_promotion_service(
    request_store: Optional[SharingRequestStoreProtocol] = None,
    strategy_store: Optional[StrategyStoreProtocol] = None,
    notification_service: Optional[NotificationServiceProtocol] = None,
    config: Optional[MultiAgentSharingConfig] = None,
) -> StrategyPromotionService:
    """Get or create the StrategyPromotionService singleton."""
    global _promotion_service
    if _promotion_service is None:
        if request_store is None or strategy_store is None:
            raise ValueError(
                "request_store and strategy_store are required for first initialization"
            )
        _promotion_service = StrategyPromotionService(
            request_store, strategy_store, notification_service, config
        )
    return _promotion_service


def reset_promotion_service() -> None:
    """Reset the StrategyPromotionService singleton (for testing)."""
    global _promotion_service
    _promotion_service = None


def get_propagator(
    agent_registry: Optional[AgentRegistryProtocol] = None,
    strategy_store: Optional[StrategyStoreProtocol] = None,
    request_store: Optional[SharingRequestStoreProtocol] = None,
    notification_service: Optional[NotificationServiceProtocol] = None,
    config: Optional[MultiAgentSharingConfig] = None,
) -> CrossAgentPropagator:
    """Get or create the CrossAgentPropagator singleton."""
    global _propagator
    if _propagator is None:
        if agent_registry is None or strategy_store is None or request_store is None:
            raise ValueError(
                "agent_registry, strategy_store, and request_store are required "
                "for first initialization"
            )
        _propagator = CrossAgentPropagator(
            agent_registry, strategy_store, request_store, notification_service, config
        )
    return _propagator


def reset_propagator() -> None:
    """Reset the CrossAgentPropagator singleton (for testing)."""
    global _propagator
    _propagator = None
