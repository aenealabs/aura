"""
Tests for capability governance middleware module.

Tests capability enforcement, caching, rate limiting, and escalation.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.capability_governance.contracts import (
    CapabilityContext,
    CapabilityDecision,
)
from src.services.capability_governance.middleware import (
    CapabilityDeniedError,
    CapabilityEnforcementMiddleware,
    CapabilityEscalationPending,
    get_capability_middleware,
    reset_capability_middleware,
)
from src.services.capability_governance.policy import (
    AgentCapabilityPolicy,
    reset_policy_repository,
)
from src.services.capability_governance.registry import reset_capability_registry

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def cleanup():
    """Reset singletons after each test."""
    yield
    reset_capability_middleware()
    reset_policy_repository()
    reset_capability_registry()


@pytest.fixture
def middleware():
    """Create a fresh middleware for each test."""
    reset_capability_middleware()
    return CapabilityEnforcementMiddleware()


# =============================================================================
# CapabilityEnforcementMiddleware Basic Tests
# =============================================================================


class TestCapabilityEnforcementMiddlewareBasic:
    """Basic tests for CapabilityEnforcementMiddleware."""

    def test_initialization(self, middleware):
        """Test middleware initialization."""
        assert middleware is not None

    @pytest.mark.asyncio
    async def test_check_allowed_safe_tool(self, middleware):
        """Test checking allowed SAFE tool."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )
        result = await middleware.check(context)

        assert result.decision == CapabilityDecision.ALLOW
        assert result.tool_name == "semantic_search"
        assert result.agent_id == "agent-123"

    @pytest.mark.asyncio
    async def test_check_denied_tool(self, middleware):
        """Test checking denied tool."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="deploy_to_production",
            action="execute",
            execution_context="sandbox",
        )
        result = await middleware.check(context)

        # CoderAgent should not be able to deploy
        assert result.decision in (CapabilityDecision.DENY, CapabilityDecision.ESCALATE)

    @pytest.mark.asyncio
    async def test_check_critical_tool_escalate(self, middleware):
        """Test checking CRITICAL tool requiring escalation."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="rotate_credentials",
            action="execute",
            execution_context="sandbox",
        )
        result = await middleware.check(context)

        # CRITICAL tools should escalate or deny for CoderAgent
        assert result.decision in (CapabilityDecision.DENY, CapabilityDecision.ESCALATE)

    def test_check_sync(self, middleware):
        """Test synchronous check."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )
        result = middleware.check_sync(context)

        assert result.decision == CapabilityDecision.ALLOW

    @pytest.mark.asyncio
    async def test_check_with_custom_policy(self, middleware):
        """Test checking with custom policy."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CustomAgent",
            tool_name="custom_tool",
            action="read",
            execution_context="sandbox",
        )
        custom_policy = AgentCapabilityPolicy(
            agent_type="CustomAgent",
            allowed_tools={"custom_tool": ["read"]},
            denied_tools=[],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.DENY,
        )
        result = await middleware.check(context, policy=custom_policy)

        assert result.decision == CapabilityDecision.ALLOW


# =============================================================================
# Caching Tests
# =============================================================================


class TestMiddlewareCaching:
    """Tests for middleware caching."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, middleware):
        """Test cache hit for repeated checks."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )

        # First check - cache miss
        result1 = await middleware.check(context)

        # Second check - should be cache hit
        result2 = await middleware.check(context)

        assert result1.decision == result2.decision
        assert result1.tool_name == result2.tool_name

    @pytest.mark.asyncio
    async def test_cache_miss_different_context(self, middleware):
        """Test cache miss for different context."""
        context1 = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )
        context2 = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="production",  # Different context
        )

        result1 = await middleware.check(context1)
        result2 = await middleware.check(context2)

        # Both should be evaluated independently
        assert result1.context == "sandbox"
        assert result2.context == "production"

    def test_clear_cache(self, middleware):
        """Test clearing the decision cache."""
        middleware._decision_cache["test_key"] = (MagicMock(), 0)
        assert len(middleware._decision_cache) == 1

        middleware.clear_cache()
        assert len(middleware._decision_cache) == 0

    def test_get_cache_stats(self, middleware):
        """Test getting cache statistics."""
        stats = middleware.get_cache_stats()

        assert "cache_size" in stats
        assert "cache_ttl_seconds" in stats
        assert "rate_tracking_keys" in stats


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestMiddlewareRateLimiting:
    """Tests for middleware rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_not_exceeded(self, middleware):
        """Test rate limit not exceeded."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )

        # First few checks should succeed
        for _ in range(5):
            result = await middleware.check(context)
            assert result.decision == CapabilityDecision.ALLOW


# =============================================================================
# Parent Check Tests
# =============================================================================


class TestMiddlewareParentCheck:
    """Tests for parent capability inheritance."""

    @pytest.mark.asyncio
    async def test_child_cannot_exceed_parent(self, middleware):
        """Test that child agent cannot exceed parent capabilities."""
        # First, check what parent can do
        parent_context = CapabilityContext(
            agent_id="parent-123",
            agent_type="CoderAgent",
            tool_name="deploy_to_production",
            action="execute",
            execution_context="sandbox",
        )
        parent_result = await middleware.check(parent_context)

        # If parent is denied, child should also be denied
        if parent_result.decision == CapabilityDecision.DENY:
            child_context = CapabilityContext(
                agent_id="child-456",
                agent_type="CoderAgent",
                tool_name="deploy_to_production",
                action="execute",
                execution_context="sandbox",
                parent_agent_id="parent-123",
            )
            child_result = await middleware.check(child_context)
            assert child_result.decision == CapabilityDecision.DENY

    def test_register_parent_capabilities(self, middleware):
        """Test registering parent capabilities."""
        capabilities = {"semantic_search:execute", "query_code_graph:read"}
        middleware.register_parent_capabilities("agent-123", capabilities)

        assert "agent-123" in middleware._parent_capabilities
        assert len(middleware._parent_capabilities["agent-123"]) == 2

    def test_unregister_parent(self, middleware):
        """Test unregistering parent."""
        middleware.register_parent_capabilities("agent-123", {"test:read"})
        assert "agent-123" in middleware._parent_capabilities

        middleware.unregister_parent("agent-123")
        assert "agent-123" not in middleware._parent_capabilities


# =============================================================================
# Escalation Tests
# =============================================================================


class TestMiddlewareEscalation:
    """Tests for escalation requests."""

    @pytest.mark.asyncio
    async def test_request_escalation(self, middleware):
        """Test requesting escalation."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="deploy_to_production",
            action="execute",
            execution_context="staging",
        )

        request = await middleware.request_escalation(
            context=context,
            justification="Need to deploy hotfix for critical bug",
            task_description="Deploy fix for CVE-2024-1234",
        )

        assert request.request_id is not None
        assert request.agent_id == "agent-123"
        assert request.requested_tool == "deploy_to_production"

    @pytest.mark.asyncio
    async def test_request_escalation_with_priority(self, middleware):
        """Test requesting escalation with priority."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="rotate_credentials",
            action="execute",
            execution_context="production",
        )

        request = await middleware.request_escalation(
            context=context,
            justification="Credential rotation needed",
            task_description="Rotate compromised credentials",
            priority="critical",
        )

        assert request.priority == "critical"


# =============================================================================
# Error Tests
# =============================================================================


class TestMiddlewareErrors:
    """Tests for middleware error handling."""

    def test_capability_denied_error(self):
        """Test CapabilityDeniedError."""
        error = CapabilityDeniedError("Not authorized for dangerous_tool")
        assert "Not authorized" in str(error)

    def test_capability_denied_error_with_result(self):
        """Test CapabilityDeniedError with result."""
        from src.services.capability_governance.contracts import CapabilityCheckResult

        result = CapabilityCheckResult(
            decision=CapabilityDecision.DENY,
            tool_name="dangerous_tool",
            agent_id="agent-123",
            agent_type="TestAgent",
            action="execute",
            context="sandbox",
            reason="Not authorized",
            policy_version="1.0.0",
            capability_source="base",
        )
        error = CapabilityDeniedError("Not authorized", result=result)
        assert error.result is not None
        assert error.result.tool_name == "dangerous_tool"

    def test_capability_escalation_pending(self):
        """Test CapabilityEscalationPending."""
        error = CapabilityEscalationPending("Awaiting HITL approval")
        assert "Awaiting" in str(error)

    def test_capability_escalation_pending_with_request(self):
        """Test CapabilityEscalationPending with request."""
        from src.services.capability_governance.contracts import (
            CapabilityEscalationRequest,
        )

        request = CapabilityEscalationRequest(
            request_id="req-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            parent_agent_id=None,
            execution_id="exec-789",
            requested_tool="critical_tool",
            requested_action="execute",
            context="production",
            justification="Need to fix bug",
            task_description="Fix critical bug",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        error = CapabilityEscalationPending("Awaiting approval", request=request)
        assert error.request is not None
        assert error.request.request_id == "req-123"


# =============================================================================
# Singleton Tests
# =============================================================================


class TestMiddlewareSingleton:
    """Tests for middleware singleton."""

    def test_get_capability_middleware(self):
        """Test getting global middleware."""
        reset_capability_middleware()
        m1 = get_capability_middleware()
        m2 = get_capability_middleware()
        assert m1 is m2

    def test_reset_capability_middleware(self):
        """Test resetting global middleware."""
        m1 = get_capability_middleware()
        reset_capability_middleware()
        m2 = get_capability_middleware()
        assert m1 is not m2


# =============================================================================
# Context-Based Tests
# =============================================================================


class TestMiddlewareContextBased:
    """Tests for context-based capability enforcement."""

    @pytest.mark.asyncio
    async def test_sandbox_context(self, middleware):
        """Test that tools are allowed in sandbox."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )
        result = await middleware.check(context)

        assert result.decision == CapabilityDecision.ALLOW


# =============================================================================
# Metrics and Audit Tests
# =============================================================================


class TestMiddlewareMetricsAudit:
    """Tests for metrics and audit functionality."""

    @pytest.mark.asyncio
    async def test_check_includes_processing_time(self, middleware):
        """Test that check result includes processing time."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )
        result = await middleware.check(context)

        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_check_includes_policy_version(self, middleware):
        """Test that check result includes policy version."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )
        result = await middleware.check(context)

        assert result.policy_version is not None
        assert len(result.policy_version) > 0

    @pytest.mark.asyncio
    async def test_check_includes_capability_source(self, middleware):
        """Test that check result includes capability source."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )
        result = await middleware.check(context)

        assert result.capability_source in (
            "base",
            "override",
            "dynamic_grant",
            "parent_inherited",
            "rate_limit",
        )


# =============================================================================
# Agent Type Tests
# =============================================================================


class TestMiddlewareAgentTypes:
    """Tests for different agent types."""

    @pytest.mark.asyncio
    async def test_coder_agent_permissions(self, middleware):
        """Test CoderAgent permissions."""
        context = CapabilityContext(
            agent_id="coder-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )
        result = await middleware.check(context)
        assert result.decision == CapabilityDecision.ALLOW

    @pytest.mark.asyncio
    async def test_reviewer_agent_permissions(self, middleware):
        """Test ReviewerAgent permissions."""
        context = CapabilityContext(
            agent_id="reviewer-123",
            agent_type="ReviewerAgent",
            tool_name="query_code_graph",
            action="read",
            execution_context="sandbox",
        )
        result = await middleware.check(context)
        assert result.decision == CapabilityDecision.ALLOW

    @pytest.mark.asyncio
    async def test_security_agent_permissions(self, middleware):
        """Test SecurityAgent permissions."""
        context = CapabilityContext(
            agent_id="security-123",
            agent_type="SecurityAgent",
            tool_name="query_audit_logs",
            action="read",
            execution_context="sandbox",
        )
        result = await middleware.check(context)
        assert result.decision == CapabilityDecision.ALLOW
