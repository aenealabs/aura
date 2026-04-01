"""
Project Aura - Capability Enforcement Middleware

Core middleware that enforces capability governance on all tool invocations.
Implements ADR-066 for runtime capability enforcement.

Enforcement Flow:
1. Extract agent identity and context
2. Resolve effective capabilities (base + dynamic grants)
3. Evaluate permission against policy
4. Return decision (ALLOW/DENY/ESCALATE/AUDIT_ONLY)
5. Audit the decision

Security Rationale:
- Synchronous enforcement prevents bypass
- Decision caching with short TTL balances performance and security
- Full audit trail enables forensic analysis

Author: Project Aura Team
Created: 2026-01-26
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

from .contracts import (
    CapabilityCheckResult,
    CapabilityContext,
    CapabilityDecision,
    CapabilityEscalationRequest,
)
from .policy import AgentCapabilityPolicy, get_policy_repository

if TYPE_CHECKING:
    from .audit import CapabilityAuditService
    from .dynamic_grants import DynamicGrantManager
    from .metrics import CapabilityMetricsPublisher

logger = logging.getLogger(__name__)


class CapabilityEnforcementMiddleware:
    """
    Middleware that enforces capability governance on all tool invocations.

    Integrates with MCPToolMixin to intercept invoke_tool() calls and
    apply policy-based access control.

    Example:
        middleware = CapabilityEnforcementMiddleware()

        context = CapabilityContext(
            agent_id="coder-agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
        )

        result = await middleware.check(context)
        if result.decision == CapabilityDecision.ALLOW:
            await tool.invoke()
    """

    def __init__(
        self,
        audit_service: Optional[CapabilityAuditService] = None,
        grant_service: Optional[DynamicGrantManager] = None,
        hitl_service: Optional[Any] = None,
        metrics_publisher: Optional[CapabilityMetricsPublisher] = None,
    ):
        """
        Initialize the middleware.

        Args:
            audit_service: Service for audit logging
            grant_service: Service for dynamic capability grants
            hitl_service: Service for HITL escalation
            metrics_publisher: Service for CloudWatch metrics
        """
        self.audit_service = audit_service
        self.grant_service = grant_service
        self.hitl_service = hitl_service
        self.metrics_publisher = metrics_publisher

        # Policy repository for cached policy lookup
        self._policy_repository = get_policy_repository()

        # Decision cache for short-term caching
        self._decision_cache: dict[str, tuple[CapabilityCheckResult, float]] = {}
        self._cache_ttl_seconds = 30  # Cache decisions for 30 seconds

        # Rate limiting tracking
        self._invocation_counts: dict[str, list[float]] = {}
        self._rate_window_seconds = 60

        # Parent capability cache for hierarchy enforcement
        self._parent_capabilities: dict[str, set[str]] = {}

    async def check(
        self,
        context: CapabilityContext,
        policy: Optional[AgentCapabilityPolicy] = None,
    ) -> CapabilityCheckResult:
        """
        Check if an agent has capability to invoke a tool.

        Args:
            context: Capability evaluation context
            policy: Optional policy override (uses cached policy if None)

        Returns:
            CapabilityCheckResult with decision and metadata
        """
        start_time = time.perf_counter()

        # Generate cache key
        cache_key = self._generate_cache_key(context)

        # Check decision cache
        cached = self._get_cached_decision(cache_key)
        if cached is not None:
            cached.processing_time_ms = (time.perf_counter() - start_time) * 1000
            return cached

        # Get policy for agent type
        if policy is None:
            policy = self._policy_repository.get_policy(context.agent_type)

        # Generate request hash for audit correlation
        request_hash = self._hash_request(context)

        # Check rate limiting first
        if not self._check_rate_limit(context, policy):
            result = CapabilityCheckResult(
                decision=CapabilityDecision.DENY,
                tool_name=context.tool_name,
                agent_id=context.agent_id,
                agent_type=context.agent_type,
                action=context.action,
                context=context.execution_context,
                reason="Rate limit exceeded",
                policy_version=policy.version,
                capability_source="rate_limit",
                request_hash=request_hash,
                parent_agent_id=context.parent_agent_id,
                execution_id=context.execution_id,
            )
            await self._finalize_result(result, start_time, cache_key)
            return result

        # Check parent capability inheritance
        if context.parent_agent_id:
            parent_result = await self._check_parent_capabilities(context, policy)
            if parent_result is not None:
                await self._finalize_result(parent_result, start_time, cache_key)
                return parent_result

        # Check dynamic grants first (most specific)
        grant_result = await self._check_dynamic_grants(context, request_hash, policy)
        if grant_result is not None:
            await self._finalize_result(grant_result, start_time, cache_key)
            return grant_result

        # Check base policy
        decision = policy.can_invoke(
            context.tool_name,
            context.action,
            context.execution_context,
        )

        # Build reason string
        reason = self._build_reason(decision, context, policy)

        result = CapabilityCheckResult(
            decision=decision,
            tool_name=context.tool_name,
            agent_id=context.agent_id,
            agent_type=context.agent_type,
            action=context.action,
            context=context.execution_context,
            reason=reason,
            policy_version=policy.version,
            capability_source="base",
            request_hash=request_hash,
            parent_agent_id=context.parent_agent_id,
            execution_id=context.execution_id,
        )

        await self._finalize_result(result, start_time, cache_key)
        return result

    def check_sync(
        self,
        context: CapabilityContext,
        policy: Optional[AgentCapabilityPolicy] = None,
    ) -> CapabilityCheckResult:
        """
        Synchronous version of capability check.

        For use in non-async contexts. Does not check dynamic grants.

        Args:
            context: Capability evaluation context
            policy: Optional policy override

        Returns:
            CapabilityCheckResult with decision
        """
        start_time = time.perf_counter()

        if policy is None:
            policy = self._policy_repository.get_policy(context.agent_type)

        request_hash = self._hash_request(context)

        # Check rate limiting
        if not self._check_rate_limit(context, policy):
            return CapabilityCheckResult(
                decision=CapabilityDecision.DENY,
                tool_name=context.tool_name,
                agent_id=context.agent_id,
                agent_type=context.agent_type,
                action=context.action,
                context=context.execution_context,
                reason="Rate limit exceeded",
                policy_version=policy.version,
                capability_source="rate_limit",
                request_hash=request_hash,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Check base policy
        decision = policy.can_invoke(
            context.tool_name,
            context.action,
            context.execution_context,
        )

        reason = self._build_reason(decision, context, policy)

        return CapabilityCheckResult(
            decision=decision,
            tool_name=context.tool_name,
            agent_id=context.agent_id,
            agent_type=context.agent_type,
            action=context.action,
            context=context.execution_context,
            reason=reason,
            policy_version=policy.version,
            capability_source="base",
            request_hash=request_hash,
            processing_time_ms=(time.perf_counter() - start_time) * 1000,
        )

    async def request_escalation(
        self,
        context: CapabilityContext,
        justification: str,
        task_description: str,
        priority: str = "normal",
    ) -> CapabilityEscalationRequest:
        """
        Create an escalation request for HITL approval.

        Args:
            context: Capability context
            justification: Why the agent needs this capability
            task_description: What task requires this capability
            priority: Request priority (low, normal, high, critical)

        Returns:
            CapabilityEscalationRequest for tracking
        """
        import uuid

        request = CapabilityEscalationRequest(
            request_id=f"cap-esc-{uuid.uuid4().hex[:12]}",
            agent_id=context.agent_id,
            agent_type=context.agent_type,
            parent_agent_id=context.parent_agent_id,
            execution_id=context.execution_id or "",
            requested_tool=context.tool_name,
            requested_action=context.action,
            context=context.execution_context,
            justification=justification,
            task_description=task_description,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            priority=priority,
        )

        logger.info(
            f"Capability escalation requested: {request.request_id} "
            f"({context.agent_id} -> {context.tool_name})"
        )

        # Notify HITL service if available
        if self.hitl_service:
            try:
                await self.hitl_service.notify_capability_escalation(request)
            except Exception as e:
                logger.error(f"Failed to notify HITL service: {e}")

        # Record metric
        if self.metrics_publisher:
            await self.metrics_publisher.record_escalation(request)

        return request

    async def _finalize_result(
        self,
        result: CapabilityCheckResult,
        start_time: float,
        cache_key: str,
    ) -> None:
        """Finalize result with timing, caching, and audit."""
        result.processing_time_ms = (time.perf_counter() - start_time) * 1000

        # Cache the decision
        self._cache_decision(cache_key, result)

        # Audit the decision
        await self._audit(result)

        # Record metric
        if self.metrics_publisher:
            await self.metrics_publisher.record_check(result)

        logger.info(
            f"Capability check: {result.agent_id} -> {result.tool_name} = "
            f"{result.decision.value} ({result.processing_time_ms:.1f}ms)"
        )

    async def _check_dynamic_grants(
        self,
        context: CapabilityContext,
        request_hash: str,
        policy: AgentCapabilityPolicy,
    ) -> Optional[CapabilityCheckResult]:
        """Check for dynamic grants that apply to this context."""
        if self.grant_service is None:
            return None

        try:
            grants = await self.grant_service.get_active_grants(context.agent_id)

            for grant in grants:
                if grant.is_applicable(
                    context.tool_name,
                    context.action,
                    context.execution_context,
                ):
                    # Increment usage count
                    await self.grant_service.increment_usage(grant.grant_id)

                    return CapabilityCheckResult(
                        decision=CapabilityDecision.ALLOW,
                        tool_name=context.tool_name,
                        agent_id=context.agent_id,
                        agent_type=context.agent_type,
                        action=context.action,
                        context=context.execution_context,
                        reason=f"Dynamic grant {grant.grant_id} matched",
                        policy_version=policy.version,
                        capability_source="dynamic_grant",
                        request_hash=request_hash,
                        parent_agent_id=context.parent_agent_id,
                        execution_id=context.execution_id,
                    )
        except Exception as e:
            logger.error(f"Error checking dynamic grants: {e}")

        return None

    async def _check_parent_capabilities(
        self,
        context: CapabilityContext,
        policy: AgentCapabilityPolicy,
    ) -> Optional[CapabilityCheckResult]:
        """
        Check that child agent doesn't exceed parent capabilities.

        A spawned agent cannot have capabilities its parent lacks.
        """
        if not context.parent_agent_id:
            return None

        # Get parent's effective capabilities
        parent_capabilities = self._parent_capabilities.get(context.parent_agent_id)

        if parent_capabilities is None:
            # Parent not tracked, allow (assume parent has capability)
            return None

        # Check if parent has this capability
        capability_key = f"{context.tool_name}:{context.action}"
        if capability_key not in parent_capabilities:
            return CapabilityCheckResult(
                decision=CapabilityDecision.DENY,
                tool_name=context.tool_name,
                agent_id=context.agent_id,
                agent_type=context.agent_type,
                action=context.action,
                context=context.execution_context,
                reason=f"Parent agent {context.parent_agent_id} lacks this capability",
                policy_version=policy.version,
                capability_source="parent_inherited",
                request_hash=self._hash_request(context),
                parent_agent_id=context.parent_agent_id,
                execution_id=context.execution_id,
            )

        return None

    def register_parent_capabilities(
        self,
        agent_id: str,
        capabilities: set[str],
    ) -> None:
        """
        Register an agent's capabilities for child inheritance checks.

        Args:
            agent_id: Agent ID
            capabilities: Set of "tool:action" strings the agent can use
        """
        self._parent_capabilities[agent_id] = capabilities
        logger.debug(
            f"Registered parent capabilities for {agent_id}: {len(capabilities)} caps"
        )

    def unregister_parent(self, agent_id: str) -> None:
        """Remove an agent from parent tracking."""
        self._parent_capabilities.pop(agent_id, None)

    def _check_rate_limit(
        self,
        context: CapabilityContext,
        policy: AgentCapabilityPolicy,
    ) -> bool:
        """
        Check if invocation is within rate limits.

        Returns:
            True if within limits, False if rate limited
        """
        key = f"{context.agent_id}:{context.tool_name}"
        now = time.time()
        window_start = now - self._rate_window_seconds

        # Get or create invocation list
        if key not in self._invocation_counts:
            self._invocation_counts[key] = []

        # Clean old entries
        self._invocation_counts[key] = [
            t for t in self._invocation_counts[key] if t > window_start
        ]

        # Check limit
        rate_limit = policy.get_rate_limit(context.tool_name)
        if len(self._invocation_counts[key]) >= rate_limit:
            logger.warning(
                f"Rate limit exceeded: {context.agent_id} -> {context.tool_name} "
                f"({len(self._invocation_counts[key])}/{rate_limit})"
            )
            return False

        # Record this invocation
        self._invocation_counts[key].append(now)
        return True

    def _build_reason(
        self,
        decision: CapabilityDecision,
        context: CapabilityContext,
        policy: AgentCapabilityPolicy,
    ) -> str:
        """Build human-readable reason for decision."""
        if decision == CapabilityDecision.ALLOW:
            return f"Allowed by {context.agent_type} policy"
        elif decision == CapabilityDecision.DENY:
            if context.tool_name in policy.denied_tools:
                return f"Tool {context.tool_name} explicitly denied for {context.agent_type}"
            elif context.execution_context not in policy.allowed_contexts:
                return f"Context {context.execution_context} not allowed for {context.agent_type}"
            else:
                return (
                    f"Tool {context.tool_name} not permitted for {context.agent_type}"
                )
        elif decision == CapabilityDecision.ESCALATE:
            return f"Tool {context.tool_name} requires HITL approval"
        else:  # AUDIT_ONLY
            return f"Allowed with audit logging for {context.tool_name}"

    def _generate_cache_key(self, context: CapabilityContext) -> str:
        """Generate cache key for decision caching."""
        return f"{context.agent_id}:{context.tool_name}:{context.action}:{context.execution_context}"

    def _get_cached_decision(self, cache_key: str) -> Optional[CapabilityCheckResult]:
        """Get cached decision if valid."""
        if cache_key in self._decision_cache:
            result, timestamp = self._decision_cache[cache_key]
            if time.time() - timestamp < self._cache_ttl_seconds:
                logger.debug(f"Cache hit for {cache_key}")
                return result
            # Expired, remove
            del self._decision_cache[cache_key]
        return None

    def _cache_decision(self, cache_key: str, result: CapabilityCheckResult) -> None:
        """Cache a decision."""
        # Only cache ALLOW and DENY decisions (not ESCALATE or AUDIT_ONLY)
        if result.decision in (CapabilityDecision.ALLOW, CapabilityDecision.DENY):
            self._decision_cache[cache_key] = (result, time.time())

            # Limit cache size
            if len(self._decision_cache) > 1000:
                # Remove oldest entries
                sorted_keys = sorted(
                    self._decision_cache.keys(),
                    key=lambda k: self._decision_cache[k][1],
                )
                for key in sorted_keys[:100]:
                    del self._decision_cache[key]

    def _hash_request(self, context: CapabilityContext) -> str:
        """Generate hash for request correlation."""
        content = (
            f"{context.agent_id}:{context.tool_name}:{context.action}:"
            f"{context.execution_context}:{time.time()}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def _audit(self, result: CapabilityCheckResult) -> None:
        """Send result to audit service."""
        if self.audit_service:
            try:
                await self.audit_service.log(result)
            except Exception as e:
                logger.error(f"Failed to audit capability check: {e}")

    def clear_cache(self) -> None:
        """Clear the decision cache."""
        self._decision_cache.clear()
        logger.info("Decision cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._decision_cache),
            "cache_ttl_seconds": self._cache_ttl_seconds,
            "rate_tracking_keys": len(self._invocation_counts),
            "parent_tracking_keys": len(self._parent_capabilities),
        }


# =============================================================================
# Exceptions
# =============================================================================


class CapabilityDeniedError(Exception):
    """Raised when an agent lacks capability to invoke a tool."""

    def __init__(self, message: str, result: Optional[CapabilityCheckResult] = None):
        super().__init__(message)
        self.result = result


class CapabilityEscalationPending(Exception):
    """Raised when capability requires HITL approval."""

    def __init__(
        self, message: str, request: Optional[CapabilityEscalationRequest] = None
    ):
        super().__init__(message)
        self.request = request


# =============================================================================
# Global Middleware Singleton
# =============================================================================

_capability_middleware: Optional[CapabilityEnforcementMiddleware] = None


def get_capability_middleware() -> CapabilityEnforcementMiddleware:
    """Get the global capability enforcement middleware."""
    global _capability_middleware
    if _capability_middleware is None:
        _capability_middleware = CapabilityEnforcementMiddleware()
    return _capability_middleware


def reset_capability_middleware() -> None:
    """Reset the global middleware (for testing)."""
    global _capability_middleware
    _capability_middleware = None
