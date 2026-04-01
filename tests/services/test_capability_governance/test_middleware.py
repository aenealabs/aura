"""
Tests for capability enforcement middleware.

Tests the core middleware that enforces capability governance on tool invocations.
"""

from unittest.mock import MagicMock

import pytest

from src.services.capability_governance import (
    AgentCapabilityPolicy,
    CapabilityContext,
    CapabilityDecision,
    CapabilityEnforcementMiddleware,
    DynamicCapabilityGrant,
)
from src.services.capability_governance.middleware import (
    CapabilityDeniedError,
    CapabilityEscalationPending,
    get_capability_middleware,
)


class TestCapabilityEnforcementMiddleware:
    """Test CapabilityEnforcementMiddleware."""

    @pytest.mark.asyncio
    async def test_check_allows_safe_tool(
        self,
        middleware: CapabilityEnforcementMiddleware,
        sample_coder_context: CapabilityContext,
    ):
        """Test that SAFE tools are allowed."""
        result = await middleware.check(sample_coder_context)
        assert result.decision == CapabilityDecision.ALLOW
        assert result.tool_name == "semantic_search"
        assert result.agent_type == "CoderAgent"

    @pytest.mark.asyncio
    async def test_check_denies_blocked_tool(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test that blocked tools are denied."""
        context = CapabilityContext(
            agent_id="coder-agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
        )
        result = await middleware.check(context)
        assert result.decision == CapabilityDecision.DENY
        assert "denied" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_check_escalates_critical_tool(
        self,
        middleware: CapabilityEnforcementMiddleware,
        sample_orchestrator_context: CapabilityContext,
    ):
        """Test that critical tools require escalation."""
        context = CapabilityContext(
            agent_id="orchestrator-001",
            agent_type="MetaOrchestrator",
            tool_name="deploy_to_production",
            action="execute",
            execution_context="production",
        )
        result = await middleware.check(context)
        assert result.decision == CapabilityDecision.ESCALATE
        assert "HITL" in result.reason or "approval" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_check_returns_audit_only_for_monitoring(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test MONITORING tools return AUDIT_ONLY."""
        context = CapabilityContext(
            agent_id="coder-agent-001",
            agent_type="CoderAgent",
            tool_name="get_agent_metrics",  # MONITORING tool
            action="read",
            execution_context="development",
        )
        result = await middleware.check(context)
        assert result.decision == CapabilityDecision.AUDIT_ONLY

    @pytest.mark.asyncio
    async def test_check_denies_wrong_context(
        self,
        middleware: CapabilityEnforcementMiddleware,
        sample_production_context: CapabilityContext,
    ):
        """Test that wrong context is denied."""
        result = await middleware.check(sample_production_context)
        assert result.decision == CapabilityDecision.DENY
        assert (
            "production" in result.reason.lower() or "context" in result.reason.lower()
        )

    @pytest.mark.asyncio
    async def test_check_with_custom_policy(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test checking with custom policy override."""
        context = CapabilityContext(
            agent_id="custom-agent-001",
            agent_type="CustomAgent",
            tool_name="custom_tool",
            action="execute",
            execution_context="development",
        )
        custom_policy = AgentCapabilityPolicy(
            agent_type="CustomAgent",
            allowed_tools={"custom_tool": ["execute"]},
        )
        result = await middleware.check(context, policy=custom_policy)
        assert result.decision == CapabilityDecision.ALLOW

    @pytest.mark.asyncio
    async def test_check_records_processing_time(
        self,
        middleware: CapabilityEnforcementMiddleware,
        sample_coder_context: CapabilityContext,
    ):
        """Test that processing time is recorded."""
        result = await middleware.check(sample_coder_context)
        assert result.processing_time_ms > 0
        assert result.processing_time_ms < 1000  # Should be fast

    @pytest.mark.asyncio
    async def test_check_generates_request_hash(
        self,
        middleware: CapabilityEnforcementMiddleware,
        sample_coder_context: CapabilityContext,
    ):
        """Test that request hash is generated."""
        result = await middleware.check(sample_coder_context)
        assert result.request_hash != ""
        assert len(result.request_hash) == 16

    @pytest.mark.asyncio
    async def test_check_audits_result(
        self,
        middleware: CapabilityEnforcementMiddleware,
        sample_coder_context: CapabilityContext,
        mock_audit_service,
    ):
        """Test that results are audited."""
        await middleware.check(sample_coder_context)
        mock_audit_service.log.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_records_metrics(
        self,
        middleware: CapabilityEnforcementMiddleware,
        sample_coder_context: CapabilityContext,
        mock_metrics_publisher,
    ):
        """Test that metrics are recorded."""
        await middleware.check(sample_coder_context)
        mock_metrics_publisher.record_check.assert_called_once()


class TestMiddlewareCaching:
    """Test middleware decision caching."""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        middleware: CapabilityEnforcementMiddleware,
        sample_coder_context: CapabilityContext,
    ):
        """Test that cached decisions are returned."""
        # First call
        result1 = await middleware.check(sample_coder_context)
        # Second call should hit cache
        result2 = await middleware.check(sample_coder_context)

        # Results should be the same
        assert result1.decision == result2.decision
        assert result1.tool_name == result2.tool_name

    @pytest.mark.asyncio
    async def test_cache_not_used_for_escalate(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test that ESCALATE decisions are not cached."""
        context = CapabilityContext(
            agent_id="orchestrator-001",
            agent_type="MetaOrchestrator",
            tool_name="deploy_to_production",
            action="execute",
            execution_context="production",
        )
        # First call
        await middleware.check(context)
        # ESCALATE should not be cached
        assert middleware._generate_cache_key(context) not in middleware._decision_cache

    @pytest.mark.asyncio
    async def test_cache_different_contexts(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test that different contexts have different cache entries."""
        context1 = CapabilityContext(
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="development",
        )
        context2 = CapabilityContext(
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="test",
        )

        key1 = middleware._generate_cache_key(context1)
        key2 = middleware._generate_cache_key(context2)
        assert key1 != key2

    def test_clear_cache(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test clearing the cache."""
        # Manually add entry
        middleware._decision_cache["test_key"] = (MagicMock(), 0)
        assert len(middleware._decision_cache) > 0
        middleware.clear_cache()
        assert len(middleware._decision_cache) == 0

    def test_get_cache_stats(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test getting cache statistics."""
        stats = middleware.get_cache_stats()
        assert "cache_size" in stats
        assert "cache_ttl_seconds" in stats
        assert "rate_tracking_keys" in stats


class TestMiddlewareRateLimiting:
    """Test middleware rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_not_exceeded(
        self,
        middleware: CapabilityEnforcementMiddleware,
        sample_coder_context: CapabilityContext,
    ):
        """Test normal usage within rate limits."""
        result = await middleware.check(sample_coder_context)
        assert result.decision == CapabilityDecision.ALLOW

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test rate limit enforcement."""
        # Create policy with low rate limit
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"test_tool": ["execute"]},
            global_rate_limit=2,  # Very low limit
        )
        context = CapabilityContext(
            agent_id="test-agent-001",
            agent_type="TestAgent",
            tool_name="test_tool",
            action="execute",
            execution_context="development",
        )

        # Exceed rate limit - clear cache after each call to force rate limit checking
        await middleware.check(context, policy=policy)
        middleware.clear_cache()
        await middleware.check(context, policy=policy)
        middleware.clear_cache()
        result = await middleware.check(context, policy=policy)

        assert result.decision == CapabilityDecision.DENY
        assert "rate limit" in result.reason.lower()


class TestMiddlewareDynamicGrants:
    """Test middleware dynamic grant handling."""

    @pytest.mark.asyncio
    async def test_dynamic_grant_allows_denied_tool(
        self,
        middleware: CapabilityEnforcementMiddleware,
        mock_grant_service,
        sample_grant: DynamicCapabilityGrant,
    ):
        """Test that dynamic grant overrides base policy denial."""
        # Setup mock to return the grant
        mock_grant_service.get_active_grants.return_value = [sample_grant]

        context = CapabilityContext(
            agent_id="coder-agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
        )

        result = await middleware.check(context)
        assert result.decision == CapabilityDecision.ALLOW
        assert result.capability_source == "dynamic_grant"
        mock_grant_service.increment_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_expired_grant_not_used(
        self,
        middleware: CapabilityEnforcementMiddleware,
        mock_grant_service,
        expired_grant: DynamicCapabilityGrant,
    ):
        """Test that expired grants are not used."""
        mock_grant_service.get_active_grants.return_value = [expired_grant]

        context = CapabilityContext(
            agent_id="coder-agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
        )

        result = await middleware.check(context)
        assert result.decision == CapabilityDecision.DENY
        assert result.capability_source != "dynamic_grant"

    @pytest.mark.asyncio
    async def test_revoked_grant_not_used(
        self,
        middleware: CapabilityEnforcementMiddleware,
        mock_grant_service,
        revoked_grant: DynamicCapabilityGrant,
    ):
        """Test that revoked grants are not used."""
        mock_grant_service.get_active_grants.return_value = [revoked_grant]

        context = CapabilityContext(
            agent_id="coder-agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
        )

        result = await middleware.check(context)
        assert result.decision == CapabilityDecision.DENY


class TestMiddlewareParentInheritance:
    """Test middleware parent capability inheritance."""

    @pytest.mark.asyncio
    async def test_child_allowed_when_parent_has_capability(
        self,
        middleware: CapabilityEnforcementMiddleware,
        child_agent_context: CapabilityContext,
    ):
        """Test child is allowed when parent has capability."""
        # Register parent capabilities
        middleware.register_parent_capabilities(
            "parent-orchestrator-001",
            {"semantic_search:execute", "query_code_graph:read"},
        )

        result = await middleware.check(child_agent_context)
        assert result.decision == CapabilityDecision.ALLOW

    @pytest.mark.asyncio
    async def test_child_denied_when_parent_lacks_capability(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test child is denied when parent lacks capability."""
        # Register parent with limited capabilities
        middleware.register_parent_capabilities(
            "parent-orchestrator-001",
            {"semantic_search:read"},  # Only read, not execute
        )

        context = CapabilityContext(
            agent_id="child-agent-001",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="development",
            parent_agent_id="parent-orchestrator-001",
        )

        result = await middleware.check(context)
        assert result.decision == CapabilityDecision.DENY
        assert "parent" in result.reason.lower()

    def test_unregister_parent(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test unregistering parent capabilities."""
        middleware.register_parent_capabilities("parent-001", {"tool:action"})
        assert "parent-001" in middleware._parent_capabilities
        middleware.unregister_parent("parent-001")
        assert "parent-001" not in middleware._parent_capabilities


class TestMiddlewareEscalation:
    """Test middleware escalation handling."""

    @pytest.mark.asyncio
    async def test_request_escalation_creates_request(
        self,
        middleware_with_hitl: CapabilityEnforcementMiddleware,
    ):
        """Test that escalation request is created."""
        context = CapabilityContext(
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
        )

        request = await middleware_with_hitl.request_escalation(
            context,
            justification="Need sandbox for testing",
            task_description="Test CVE-2026-1234 patch",
        )

        assert request.request_id.startswith("cap-esc-")
        assert request.agent_id == "agent-001"
        assert request.requested_tool == "provision_sandbox"
        assert request.status == "pending"

    @pytest.mark.asyncio
    async def test_request_escalation_notifies_hitl(
        self,
        middleware_with_hitl: CapabilityEnforcementMiddleware,
        mock_hitl_service,
    ):
        """Test that HITL service is notified."""
        context = CapabilityContext(
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
        )

        await middleware_with_hitl.request_escalation(
            context,
            justification="Test",
            task_description="Test",
        )

        mock_hitl_service.notify_capability_escalation.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_escalation_with_priority(
        self,
        middleware_with_hitl: CapabilityEnforcementMiddleware,
    ):
        """Test escalation request with priority."""
        context = CapabilityContext(
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
        )

        request = await middleware_with_hitl.request_escalation(
            context,
            justification="Critical security patch",
            task_description="CVE remediation",
            priority="critical",
        )

        assert request.priority == "critical"


class TestSynchronousCheck:
    """Test synchronous capability check."""

    def test_check_sync_allows_safe_tool(
        self,
        middleware: CapabilityEnforcementMiddleware,
        sample_coder_context: CapabilityContext,
    ):
        """Test synchronous check allows SAFE tools."""
        result = middleware.check_sync(sample_coder_context)
        assert result.decision == CapabilityDecision.ALLOW

    def test_check_sync_denies_blocked_tool(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test synchronous check denies blocked tools."""
        context = CapabilityContext(
            agent_id="coder-agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
        )
        result = middleware.check_sync(context)
        assert result.decision == CapabilityDecision.DENY

    def test_check_sync_rate_limit(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test synchronous check enforces rate limits."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"test_tool": ["execute"]},
            global_rate_limit=2,
        )
        context = CapabilityContext(
            agent_id="test-agent-002",  # Use unique agent_id to avoid cache/rate conflicts
            agent_type="TestAgent",
            tool_name="test_tool",
            action="execute",
            execution_context="development",
        )

        # Note: check_sync doesn't use the decision cache, but shares rate limit tracking
        middleware.check_sync(context, policy=policy)
        middleware.check_sync(context, policy=policy)
        result = middleware.check_sync(context, policy=policy)

        assert result.decision == CapabilityDecision.DENY


class TestExceptions:
    """Test middleware exceptions."""

    def test_capability_denied_error(self):
        """Test CapabilityDeniedError."""
        error = CapabilityDeniedError("Access denied")
        assert str(error) == "Access denied"
        assert error.result is None

    def test_capability_denied_error_with_result(
        self,
        sample_check_result,
    ):
        """Test CapabilityDeniedError with result."""
        error = CapabilityDeniedError("Access denied", result=sample_check_result)
        assert error.result is not None
        assert error.result.decision == CapabilityDecision.ALLOW

    def test_capability_escalation_pending(self):
        """Test CapabilityEscalationPending."""
        error = CapabilityEscalationPending("Requires approval")
        assert str(error) == "Requires approval"
        assert error.request is None

    def test_capability_escalation_pending_with_request(
        self,
        sample_escalation_request,
    ):
        """Test CapabilityEscalationPending with request."""
        error = CapabilityEscalationPending(
            "Requires approval",
            request=sample_escalation_request,
        )
        assert error.request is not None
        assert error.request.status == "pending"


class TestGlobalMiddleware:
    """Test global middleware singleton."""

    def test_get_capability_middleware_singleton(self):
        """Test global middleware is singleton."""
        middleware1 = get_capability_middleware()
        middleware2 = get_capability_middleware()
        assert middleware1 is middleware2


class TestSecurityScenarios:
    """Test security-related scenarios."""

    @pytest.mark.asyncio
    async def test_agent_cannot_spoof_type(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test that agent_id spoofing doesn't elevate privileges."""
        # Agent claims to be admin but type is CoderAgent
        context = CapabilityContext(
            agent_id="admin-agent-spoofed",  # Fake admin ID
            agent_type="CoderAgent",  # Real type
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
        )

        result = await middleware.check(context)
        # Should use CoderAgent policy, not admin
        assert result.decision == CapabilityDecision.DENY

    @pytest.mark.asyncio
    async def test_production_context_restrictions(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test that production context has strict restrictions."""
        # Even admin agent in production context for dangerous operations
        context = CapabilityContext(
            agent_id="admin-agent-001",
            agent_type="AdminAgent",
            tool_name="deploy_to_production",
            action="execute",
            execution_context="production",
        )

        result = await middleware.check(context)
        # Should escalate for critical operations
        assert result.decision in (
            CapabilityDecision.ESCALATE,
            CapabilityDecision.DENY,
        )

    @pytest.mark.asyncio
    async def test_child_cannot_exceed_parent(
        self,
        middleware: CapabilityEnforcementMiddleware,
    ):
        """Test privilege escalation through child agents is prevented."""
        # Parent has limited capabilities
        middleware.register_parent_capabilities(
            "limited-parent-001",
            {"semantic_search:read"},
        )

        # Child is AdminAgent type but parent is limited
        context = CapabilityContext(
            agent_id="admin-child-001",
            agent_type="AdminAgent",
            tool_name="provision_sandbox",
            action="execute",
            execution_context="development",
            parent_agent_id="limited-parent-001",
        )

        result = await middleware.check(context)
        # Child cannot have more than parent
        assert result.decision == CapabilityDecision.DENY
        assert "parent" in result.reason.lower()

    @pytest.mark.parametrize(
        "agent_type,tool,context,expected",
        [
            ("CoderAgent", "semantic_search", "development", CapabilityDecision.ALLOW),
            ("CoderAgent", "provision_sandbox", "development", CapabilityDecision.DENY),
            ("CoderAgent", "semantic_search", "production", CapabilityDecision.DENY),
            # ReviewerAgent allows query_code_graph with "read" action only, but test uses "execute"
            (
                "ReviewerAgent",
                "query_code_graph",
                "development",
                CapabilityDecision.DENY,
            ),
            ("ReviewerAgent", "commit_changes", "development", CapabilityDecision.DENY),
            ("RedTeamAgent", "provision_sandbox", "sandbox", CapabilityDecision.ALLOW),
            (
                "RedTeamAgent",
                "deploy_to_production",
                "sandbox",
                CapabilityDecision.DENY,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_security_matrix(
        self,
        middleware: CapabilityEnforcementMiddleware,
        agent_type: str,
        tool: str,
        context: str,
        expected: CapabilityDecision,
    ):
        """Test security decision matrix."""
        cap_context = CapabilityContext(
            agent_id=f"{agent_type.lower()}-test-001",
            agent_type=agent_type,
            tool_name=tool,
            action="execute",
            execution_context=context,
        )

        result = await middleware.check(cap_context)
        assert result.decision == expected
