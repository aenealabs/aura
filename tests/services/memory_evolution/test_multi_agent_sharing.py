"""
Tests for ADR-080 Phase 6: Multi-Agent Memory Sharing.

Tests cover:
- Strategy nomination and approval workflows
- Cross-agent propagation
- Relevance filtering
- Rate limiting and security controls
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.services.memory_evolution.contracts import AbstractedStrategy
from src.services.memory_evolution.multi_agent_sharing import (
    AcceptanceDecision,
    AgentAcceptance,
    ApprovalType,
    CrossAgentPropagator,
    MultiAgentSharingConfig,
    PropagationResult,
    PropagationScope,
    SharingPolicy,
    SharingRequest,
    SharingStatus,
    StrategyPromotionService,
    get_promotion_service,
    get_propagator,
    reset_promotion_service,
    reset_propagator,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before and after each test."""
    reset_promotion_service()
    reset_propagator()
    yield
    reset_promotion_service()
    reset_propagator()


@pytest.fixture
def mock_request_store():
    """Create a mock request store."""
    store = AsyncMock()
    store.save_request = AsyncMock()
    store.get_request = AsyncMock(return_value=None)
    store.update_request = AsyncMock()
    store.get_pending_requests = AsyncMock(return_value=[])
    store.count_requests_since = AsyncMock(return_value=0)
    return store


@pytest.fixture
def mock_strategy_store():
    """Create a mock strategy store."""
    store = AsyncMock()
    store.get_strategy = AsyncMock(
        return_value=AbstractedStrategy(
            strategy_id="strat-123",
            title="Debug Pattern",
            description="Step-by-step debugging approach",
            source_memory_ids=["mem-1", "mem-2"],
            applicability_conditions=["debugging", "error analysis"],
            key_steps=["Reproduce", "Isolate", "Fix"],
            success_indicators=["Bug resolved"],
            embedding=[0.1] * 128,
            confidence=0.92,
            tenant_id="tenant-1",
            security_domain="domain-1",
        )
    )
    store.get_strategy_metrics = AsyncMock(
        return_value={"success_rate": 0.85, "usage_count": 10}
    )
    store.copy_strategy_to_agent = AsyncMock(return_value="new-strat-456")
    return store


@pytest.fixture
def mock_agent_registry():
    """Create a mock agent registry."""
    registry = AsyncMock()
    registry.get_agent = AsyncMock(
        return_value={
            "agent_id": "agent-1",
            "tenant_id": "tenant-1",
            "agent_type": "coder",
            "domain": "development",
        }
    )
    registry.get_agents_by_tenant = AsyncMock(
        return_value=[
            {"agent_id": "agent-2", "tenant_id": "tenant-1", "agent_type": "reviewer"},
            {"agent_id": "agent-3", "tenant_id": "tenant-1", "agent_type": "tester"},
        ]
    )
    registry.get_agents_by_domain = AsyncMock(
        return_value=[
            {
                "agent_id": "agent-2",
                "tenant_id": "tenant-1",
                "security_domain": "domain-1",
            },
        ]
    )
    registry.get_agents_by_type = AsyncMock(
        return_value=[
            {"agent_id": "agent-4", "tenant_id": "tenant-1", "agent_type": "coder"},
        ]
    )
    return registry


@pytest.fixture
def mock_notification_service():
    """Create a mock notification service."""
    service = AsyncMock()
    service.notify_approval_required = AsyncMock()
    service.notify_strategy_shared = AsyncMock()
    return service


@pytest.fixture
def default_config():
    """Create default configuration."""
    return MultiAgentSharingConfig()


@pytest.fixture
def sample_strategy():
    """Create a sample strategy."""
    return AbstractedStrategy(
        strategy_id="strat-123",
        title="Debug Pattern",
        description="Step-by-step debugging approach",
        source_memory_ids=["mem-1", "mem-2"],
        applicability_conditions=["debugging", "error analysis", "coder"],
        key_steps=["Reproduce", "Isolate", "Fix"],
        success_indicators=["Bug resolved"],
        embedding=[0.1] * 128,
        confidence=0.92,
        tenant_id="tenant-1",
        security_domain="domain-1",
    )


# =============================================================================
# SHARING STATUS ENUM TESTS
# =============================================================================


class TestSharingStatus:
    """Tests for SharingStatus enum."""

    def test_all_statuses_defined(self):
        """Verify all statuses are defined."""
        assert SharingStatus.PENDING.value == "pending"
        assert SharingStatus.APPROVED.value == "approved"
        assert SharingStatus.REJECTED.value == "rejected"
        assert SharingStatus.PROPAGATING.value == "propagating"
        assert SharingStatus.COMPLETED.value == "completed"
        assert SharingStatus.FAILED.value == "failed"
        assert SharingStatus.EXPIRED.value == "expired"

    def test_status_count(self):
        """Verify expected number of statuses."""
        assert len(SharingStatus) == 7


class TestApprovalType:
    """Tests for ApprovalType enum."""

    def test_all_types_defined(self):
        """Verify all approval types are defined."""
        assert ApprovalType.AUTO.value == "auto"
        assert ApprovalType.HUMAN.value == "human"
        assert ApprovalType.PEER.value == "peer"
        assert ApprovalType.ADMIN.value == "admin"


class TestPropagationScope:
    """Tests for PropagationScope enum."""

    def test_all_scopes_defined(self):
        """Verify all scopes are defined."""
        assert PropagationScope.SAME_AGENT_TYPE.value == "same_agent_type"
        assert PropagationScope.SAME_DOMAIN.value == "same_domain"
        assert PropagationScope.SAME_TENANT.value == "same_tenant"
        assert PropagationScope.GLOBAL.value == "global"


class TestAcceptanceDecision:
    """Tests for AcceptanceDecision enum."""

    def test_all_decisions_defined(self):
        """Verify all decisions are defined."""
        assert AcceptanceDecision.ACCEPTED.value == "accepted"
        assert AcceptanceDecision.REJECTED.value == "rejected"
        assert AcceptanceDecision.DEFERRED.value == "deferred"
        assert AcceptanceDecision.FILTERED.value == "filtered"


# =============================================================================
# SHARING POLICY TESTS
# =============================================================================


class TestSharingPolicy:
    """Tests for SharingPolicy dataclass."""

    def test_default_values(self):
        """Test default policy values."""
        policy = SharingPolicy()
        assert policy.auto_approve_threshold == 0.9
        assert policy.min_success_rate == 0.8
        assert policy.min_usage_count == 5
        assert policy.max_propagation_batch == 50
        assert policy.rate_limit_per_hour == 10
        assert policy.allow_cross_domain is False

    def test_custom_values(self):
        """Test custom policy values."""
        policy = SharingPolicy(
            auto_approve_threshold=0.95,
            min_usage_count=10,
            allow_cross_domain=True,
        )
        assert policy.auto_approve_threshold == 0.95
        assert policy.min_usage_count == 10
        assert policy.allow_cross_domain is True

    def test_to_dict(self):
        """Test serialization to dictionary."""
        policy = SharingPolicy()
        d = policy.to_dict()
        assert "auto_approve_threshold" in d
        assert "min_success_rate" in d
        assert "rate_limit_per_hour" in d


# =============================================================================
# SHARING REQUEST TESTS
# =============================================================================


class TestSharingRequest:
    """Tests for SharingRequest dataclass."""

    def test_valid_request(self):
        """Test creating a valid request."""
        request = SharingRequest(
            request_id="share-123",
            strategy_id="strat-456",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
            scope=PropagationScope.SAME_DOMAIN,
            confidence=0.9,
            success_rate=0.85,
        )
        assert request.request_id == "share-123"
        assert request.status == SharingStatus.PENDING
        assert request.approval_type == ApprovalType.AUTO

    def test_invalid_confidence_raises(self):
        """Test that invalid confidence raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be"):
            SharingRequest(
                request_id="share-123",
                strategy_id="strat-456",
                source_agent_id="agent-1",
                tenant_id="tenant-1",
                security_domain="domain-1",
                scope=PropagationScope.SAME_DOMAIN,
                confidence=1.5,
            )

    def test_invalid_success_rate_raises(self):
        """Test that invalid success rate raises ValueError."""
        with pytest.raises(ValueError, match="Success rate must be"):
            SharingRequest(
                request_id="share-123",
                strategy_id="strat-456",
                source_agent_id="agent-1",
                tenant_id="tenant-1",
                security_domain="domain-1",
                scope=PropagationScope.SAME_DOMAIN,
                success_rate=-0.1,
            )

    def test_to_dict(self):
        """Test serialization to dictionary."""
        request = SharingRequest(
            request_id="share-123",
            strategy_id="strat-456",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
            scope=PropagationScope.SAME_TENANT,
        )
        d = request.to_dict()
        assert d["request_id"] == "share-123"
        assert d["scope"] == "same_tenant"
        assert d["status"] == "pending"


# =============================================================================
# PROPAGATION RESULT TESTS
# =============================================================================


class TestPropagationResult:
    """Tests for PropagationResult dataclass."""

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        result = PropagationResult(
            request_id="share-123",
            strategy_id="strat-456",
            agents_targeted=10,
            agents_received=8,
            agents_accepted=6,
            agents_rejected=2,
            agents_failed=2,
        )
        assert result.success_rate == 0.8
        assert result.acceptance_rate == 0.75

    def test_zero_targeted(self):
        """Test rates with zero targeted agents."""
        result = PropagationResult(
            request_id="share-123",
            strategy_id="strat-456",
            agents_targeted=0,
            agents_received=0,
            agents_accepted=0,
            agents_rejected=0,
            agents_failed=0,
        )
        assert result.success_rate == 0.0
        assert result.acceptance_rate == 0.0

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = PropagationResult(
            request_id="share-123",
            strategy_id="strat-456",
            agents_targeted=10,
            agents_received=8,
            agents_accepted=6,
            agents_rejected=2,
            agents_failed=0,
        )
        d = result.to_dict()
        assert d["success_rate"] == 0.8
        assert d["acceptance_rate"] == 0.75


# =============================================================================
# AGENT ACCEPTANCE TESTS
# =============================================================================


class TestAgentAcceptance:
    """Tests for AgentAcceptance dataclass."""

    def test_valid_acceptance(self):
        """Test creating a valid acceptance."""
        acceptance = AgentAcceptance(
            agent_id="agent-1",
            strategy_id="strat-123",
            request_id="share-456",
            decision=AcceptanceDecision.ACCEPTED,
            relevance_score=0.85,
        )
        assert acceptance.agent_id == "agent-1"
        assert acceptance.decision == AcceptanceDecision.ACCEPTED

    def test_to_dict(self):
        """Test serialization to dictionary."""
        acceptance = AgentAcceptance(
            agent_id="agent-1",
            strategy_id="strat-123",
            request_id="share-456",
            decision=AcceptanceDecision.REJECTED,
            reasoning="Not relevant to my tasks",
        )
        d = acceptance.to_dict()
        assert d["decision"] == "rejected"
        assert d["reasoning"] == "Not relevant to my tasks"


# =============================================================================
# MULTI-AGENT SHARING CONFIG TESTS
# =============================================================================


class TestMultiAgentSharingConfig:
    """Tests for MultiAgentSharingConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = MultiAgentSharingConfig()
        assert config.enable_auto_approval is True
        assert config.enable_peer_approval is False
        assert config.request_expiry_hours == 24
        assert config.max_pending_requests == 100
        assert config.propagation_batch_size == 10
        assert config.relevance_threshold == 0.5

    def test_custom_values(self):
        """Test custom configuration values."""
        config = MultiAgentSharingConfig(
            enable_auto_approval=False,
            request_expiry_hours=48,
            relevance_threshold=0.7,
        )
        assert config.enable_auto_approval is False
        assert config.request_expiry_hours == 48
        assert config.relevance_threshold == 0.7


# =============================================================================
# STRATEGY PROMOTION SERVICE TESTS
# =============================================================================


class TestStrategyPromotionService:
    """Tests for StrategyPromotionService."""

    @pytest.mark.asyncio
    async def test_nominate_auto_approve(self, mock_request_store, mock_strategy_store):
        """Test nomination with auto-approval."""
        service = StrategyPromotionService(mock_request_store, mock_strategy_store)

        request = await service.nominate_for_sharing(
            strategy_id="strat-123",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
        )

        assert request.status == SharingStatus.APPROVED
        assert request.approved_by == "auto"
        mock_request_store.save_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_nominate_human_approval(
        self, mock_request_store, mock_strategy_store, mock_notification_service
    ):
        """Test nomination requiring human approval."""
        # Set low confidence to require human approval
        mock_strategy_store.get_strategy = AsyncMock(
            return_value=AbstractedStrategy(
                strategy_id="strat-123",
                title="Test",
                description="Test",
                source_memory_ids=["mem-1"],
                applicability_conditions=[],
                key_steps=[],
                success_indicators=[],
                embedding=[0.1] * 128,
                confidence=0.7,  # Below auto-approve threshold
                tenant_id="tenant-1",
                security_domain="domain-1",
            )
        )

        config = MultiAgentSharingConfig(enable_auto_approval=True)
        service = StrategyPromotionService(
            mock_request_store, mock_strategy_store, mock_notification_service, config
        )

        request = await service.nominate_for_sharing(
            strategy_id="strat-123",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
        )

        assert request.status == SharingStatus.PENDING
        assert request.approval_type == ApprovalType.HUMAN

    @pytest.mark.asyncio
    async def test_nominate_rate_limited(self, mock_request_store, mock_strategy_store):
        """Test nomination fails when rate limited."""
        mock_request_store.count_requests_since = AsyncMock(return_value=15)

        service = StrategyPromotionService(mock_request_store, mock_strategy_store)

        with pytest.raises(Exception, match="Rate limit exceeded"):
            await service.nominate_for_sharing(
                strategy_id="strat-123",
                source_agent_id="agent-1",
                tenant_id="tenant-1",
                security_domain="domain-1",
            )

    @pytest.mark.asyncio
    async def test_nominate_strategy_not_found(
        self, mock_request_store, mock_strategy_store
    ):
        """Test nomination fails when strategy not found."""
        mock_strategy_store.get_strategy = AsyncMock(return_value=None)

        service = StrategyPromotionService(mock_request_store, mock_strategy_store)

        with pytest.raises(Exception, match="Strategy not found"):
            await service.nominate_for_sharing(
                strategy_id="strat-missing",
                source_agent_id="agent-1",
                tenant_id="tenant-1",
                security_domain="domain-1",
            )

    @pytest.mark.asyncio
    async def test_nominate_tenant_mismatch(
        self, mock_request_store, mock_strategy_store
    ):
        """Test nomination fails with tenant mismatch."""
        service = StrategyPromotionService(mock_request_store, mock_strategy_store)

        with pytest.raises(Exception, match="different tenant"):
            await service.nominate_for_sharing(
                strategy_id="strat-123",
                source_agent_id="agent-1",
                tenant_id="different-tenant",
                security_domain="domain-1",
            )

    @pytest.mark.asyncio
    async def test_nominate_low_success_rate(
        self, mock_request_store, mock_strategy_store
    ):
        """Test nomination fails with low success rate."""
        mock_strategy_store.get_strategy_metrics = AsyncMock(
            return_value={"success_rate": 0.5, "usage_count": 10}
        )

        service = StrategyPromotionService(mock_request_store, mock_strategy_store)

        with pytest.raises(Exception, match="success rate.*below minimum"):
            await service.nominate_for_sharing(
                strategy_id="strat-123",
                source_agent_id="agent-1",
                tenant_id="tenant-1",
                security_domain="domain-1",
            )

    @pytest.mark.asyncio
    async def test_nominate_low_usage_count(
        self, mock_request_store, mock_strategy_store
    ):
        """Test nomination fails with low usage count."""
        mock_strategy_store.get_strategy_metrics = AsyncMock(
            return_value={"success_rate": 0.9, "usage_count": 2}
        )

        service = StrategyPromotionService(mock_request_store, mock_strategy_store)

        with pytest.raises(Exception, match="usage count.*below minimum"):
            await service.nominate_for_sharing(
                strategy_id="strat-123",
                source_agent_id="agent-1",
                tenant_id="tenant-1",
                security_domain="domain-1",
            )

    @pytest.mark.asyncio
    async def test_approve_request(self, mock_request_store, mock_strategy_store):
        """Test approving a request."""
        pending_request = SharingRequest(
            request_id="share-123",
            strategy_id="strat-456",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
            scope=PropagationScope.SAME_DOMAIN,
            status=SharingStatus.PENDING,
        )
        mock_request_store.get_request = AsyncMock(return_value=pending_request)
        mock_request_store.update_request = AsyncMock(
            return_value=SharingRequest(
                **{**pending_request.to_dict(), "status": SharingStatus.APPROVED.value}
            )
        )

        service = StrategyPromotionService(mock_request_store, mock_strategy_store)
        result = await service.approve_request(
            request_id="share-123",
            approver_id="admin-1",
            tenant_id="tenant-1",
        )

        mock_request_store.update_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_wrong_tenant(self, mock_request_store, mock_strategy_store):
        """Test approve fails with wrong tenant."""
        pending_request = SharingRequest(
            request_id="share-123",
            strategy_id="strat-456",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
            scope=PropagationScope.SAME_DOMAIN,
        )
        mock_request_store.get_request = AsyncMock(return_value=pending_request)

        service = StrategyPromotionService(mock_request_store, mock_strategy_store)

        with pytest.raises(Exception, match="different tenant"):
            await service.approve_request(
                request_id="share-123",
                approver_id="admin-1",
                tenant_id="different-tenant",
            )

    @pytest.mark.asyncio
    async def test_reject_request(self, mock_request_store, mock_strategy_store):
        """Test rejecting a request."""
        pending_request = SharingRequest(
            request_id="share-123",
            strategy_id="strat-456",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
            scope=PropagationScope.SAME_DOMAIN,
        )
        mock_request_store.get_request = AsyncMock(return_value=pending_request)
        mock_request_store.update_request = AsyncMock()

        service = StrategyPromotionService(mock_request_store, mock_strategy_store)
        await service.reject_request(
            request_id="share-123",
            rejector_id="admin-1",
            tenant_id="tenant-1",
            reason="Strategy not suitable for sharing",
        )

        mock_request_store.update_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pending_requests(self, mock_request_store, mock_strategy_store):
        """Test getting pending requests."""
        pending = [
            SharingRequest(
                request_id="share-1",
                strategy_id="strat-1",
                source_agent_id="agent-1",
                tenant_id="tenant-1",
                security_domain="domain-1",
                scope=PropagationScope.SAME_DOMAIN,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
            ),
            SharingRequest(
                request_id="share-2",
                strategy_id="strat-2",
                source_agent_id="agent-2",
                tenant_id="tenant-1",
                security_domain="domain-1",
                scope=PropagationScope.SAME_DOMAIN,
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            ),
        ]
        mock_request_store.get_pending_requests = AsyncMock(return_value=pending)
        mock_request_store.update_request = AsyncMock()

        service = StrategyPromotionService(mock_request_store, mock_strategy_store)
        result = await service.get_pending_requests("tenant-1")

        # Should filter out expired request
        assert len(result) == 1
        assert result[0].request_id == "share-1"


# =============================================================================
# CROSS-AGENT PROPAGATOR TESTS
# =============================================================================


class TestCrossAgentPropagator:
    """Tests for CrossAgentPropagator."""

    @pytest.mark.asyncio
    async def test_propagate_success(
        self,
        mock_agent_registry,
        mock_strategy_store,
        mock_request_store,
        mock_notification_service,
    ):
        """Test successful propagation."""
        approved_request = SharingRequest(
            request_id="share-123",
            strategy_id="strat-456",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
            scope=PropagationScope.SAME_TENANT,
            status=SharingStatus.APPROVED,
        )
        mock_request_store.get_request = AsyncMock(return_value=approved_request)
        mock_request_store.update_request = AsyncMock()

        config = MultiAgentSharingConfig(enable_relevance_filtering=False)
        propagator = CrossAgentPropagator(
            mock_agent_registry,
            mock_strategy_store,
            mock_request_store,
            mock_notification_service,
            config,
        )

        result = await propagator.propagate("share-123")

        assert result.agents_targeted == 2
        assert result.agents_received == 2
        assert result.agents_accepted == 2
        assert result.agents_failed == 0

    @pytest.mark.asyncio
    async def test_propagate_not_approved(
        self,
        mock_agent_registry,
        mock_strategy_store,
        mock_request_store,
    ):
        """Test propagation fails for non-approved request."""
        pending_request = SharingRequest(
            request_id="share-123",
            strategy_id="strat-456",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
            scope=PropagationScope.SAME_TENANT,
            status=SharingStatus.PENDING,
        )
        mock_request_store.get_request = AsyncMock(return_value=pending_request)

        propagator = CrossAgentPropagator(
            mock_agent_registry, mock_strategy_store, mock_request_store
        )

        with pytest.raises(Exception, match="Cannot propagate"):
            await propagator.propagate("share-123")

    @pytest.mark.asyncio
    async def test_propagate_with_relevance_filtering(
        self,
        mock_agent_registry,
        mock_strategy_store,
        mock_request_store,
        sample_strategy,
    ):
        """Test propagation with relevance filtering."""
        approved_request = SharingRequest(
            request_id="share-123",
            strategy_id="strat-456",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
            scope=PropagationScope.SAME_TENANT,
            status=SharingStatus.APPROVED,
        )
        mock_request_store.get_request = AsyncMock(return_value=approved_request)
        mock_request_store.update_request = AsyncMock()
        mock_strategy_store.get_strategy = AsyncMock(return_value=sample_strategy)

        # One agent will have high relevance (coder), one won't
        mock_agent_registry.get_agents_by_tenant = AsyncMock(
            return_value=[
                {"agent_id": "agent-2", "tenant_id": "tenant-1", "agent_type": "coder"},
                {
                    "agent_id": "agent-3",
                    "tenant_id": "tenant-1",
                    "agent_type": "unrelated",
                },
            ]
        )

        config = MultiAgentSharingConfig(
            enable_relevance_filtering=True,
            relevance_threshold=0.6,
        )
        propagator = CrossAgentPropagator(
            mock_agent_registry,
            mock_strategy_store,
            mock_request_store,
            config=config,
        )

        result = await propagator.propagate("share-123")

        # One agent should be accepted (coder), one rejected (unrelated)
        assert result.agents_targeted == 2
        assert result.agents_accepted == 1
        assert result.agents_rejected == 1

    @pytest.mark.asyncio
    async def test_propagate_specific_targets(
        self,
        mock_agent_registry,
        mock_strategy_store,
        mock_request_store,
    ):
        """Test propagation to specific target agents."""
        approved_request = SharingRequest(
            request_id="share-123",
            strategy_id="strat-456",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
            scope=PropagationScope.SAME_TENANT,
            status=SharingStatus.APPROVED,
            target_agent_ids=["agent-5", "agent-6"],
        )
        mock_request_store.get_request = AsyncMock(return_value=approved_request)
        mock_request_store.update_request = AsyncMock()

        # Mock individual agent lookups
        mock_agent_registry.get_agent = AsyncMock(
            side_effect=lambda aid: {
                "agent_id": aid,
                "tenant_id": "tenant-1",
                "agent_type": "coder",
            }
        )

        config = MultiAgentSharingConfig(enable_relevance_filtering=False)
        propagator = CrossAgentPropagator(
            mock_agent_registry,
            mock_strategy_store,
            mock_request_store,
            config=config,
        )

        result = await propagator.propagate("share-123")

        assert result.agents_targeted == 2

    @pytest.mark.asyncio
    async def test_propagate_no_eligible_agents(
        self,
        mock_agent_registry,
        mock_strategy_store,
        mock_request_store,
    ):
        """Test propagation with no eligible agents."""
        approved_request = SharingRequest(
            request_id="share-123",
            strategy_id="strat-456",
            source_agent_id="agent-1",
            tenant_id="tenant-1",
            security_domain="domain-1",
            scope=PropagationScope.SAME_TENANT,
            status=SharingStatus.APPROVED,
        )
        mock_request_store.get_request = AsyncMock(return_value=approved_request)
        mock_request_store.update_request = AsyncMock()
        mock_agent_registry.get_agents_by_tenant = AsyncMock(return_value=[])

        propagator = CrossAgentPropagator(
            mock_agent_registry, mock_strategy_store, mock_request_store
        )

        result = await propagator.propagate("share-123")

        assert result.agents_targeted == 0
        assert result.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_record_acceptance(
        self,
        mock_agent_registry,
        mock_strategy_store,
        mock_request_store,
    ):
        """Test recording acceptance decision."""
        propagator = CrossAgentPropagator(
            mock_agent_registry, mock_strategy_store, mock_request_store
        )

        acceptance = await propagator.record_acceptance(
            agent_id="agent-2",
            strategy_id="strat-123",
            request_id="share-456",
            decision=AcceptanceDecision.ACCEPTED,
            relevance_score=0.85,
            reasoning="Highly relevant to my tasks",
        )

        assert acceptance.agent_id == "agent-2"
        assert acceptance.decision == AcceptanceDecision.ACCEPTED
        assert acceptance.relevance_score == 0.85


# =============================================================================
# SINGLETON MANAGEMENT TESTS
# =============================================================================


class TestSingletonManagement:
    """Tests for singleton getter/reset functions."""

    def test_get_promotion_service_requires_deps(self):
        """Test that get_promotion_service requires dependencies."""
        with pytest.raises(ValueError, match="request_store and strategy_store"):
            get_promotion_service()

    def test_get_promotion_service_creates_singleton(
        self, mock_request_store, mock_strategy_store
    ):
        """Test that get_promotion_service creates singleton."""
        service1 = get_promotion_service(mock_request_store, mock_strategy_store)
        service2 = get_promotion_service()
        assert service1 is service2

    def test_reset_promotion_service(self, mock_request_store, mock_strategy_store):
        """Test that reset_promotion_service clears singleton."""
        service1 = get_promotion_service(mock_request_store, mock_strategy_store)
        reset_promotion_service()
        service2 = get_promotion_service(mock_request_store, mock_strategy_store)
        assert service1 is not service2

    def test_get_propagator_requires_deps(self):
        """Test that get_propagator requires dependencies."""
        with pytest.raises(ValueError, match="agent_registry"):
            get_propagator()

    def test_get_propagator_creates_singleton(
        self, mock_agent_registry, mock_strategy_store, mock_request_store
    ):
        """Test that get_propagator creates singleton."""
        prop1 = get_propagator(
            mock_agent_registry, mock_strategy_store, mock_request_store
        )
        prop2 = get_propagator()
        assert prop1 is prop2

    def test_reset_propagator(
        self, mock_agent_registry, mock_strategy_store, mock_request_store
    ):
        """Test that reset_propagator clears singleton."""
        prop1 = get_propagator(
            mock_agent_registry, mock_strategy_store, mock_request_store
        )
        reset_propagator()
        prop2 = get_propagator(
            mock_agent_registry, mock_strategy_store, mock_request_store
        )
        assert prop1 is not prop2
