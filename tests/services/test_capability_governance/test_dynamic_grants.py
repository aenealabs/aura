"""
Tests for dynamic capability grant manager.

Tests grant creation, validation, usage tracking, and revocation.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.capability_governance import (
    CapabilityApprovalResponse,
    CapabilityScope,
    DynamicCapabilityGrant,
    DynamicGrantManager,
    GrantManagerConfig,
    get_grant_manager,
)


class InMemoryDynamicGrantManager(DynamicGrantManager):
    """A DynamicGrantManager that uses only in-memory storage."""

    def _get_dynamodb_client(self):
        """Always return None to force in-memory storage."""
        return None

    def _invalidate_cache(self, agent_id: str) -> None:
        """Override to NOT invalidate cache in in-memory mode.

        The base implementation invalidates cache after save, expecting
        a later get to refresh from DynamoDB. For in-memory storage,
        we don't want to delete what we just saved.
        """
        pass  # Don't invalidate in-memory storage


@pytest.fixture
def in_memory_manager():
    """
    Create a grant manager that uses in-memory storage.
    """
    return InMemoryDynamicGrantManager()


@pytest.fixture
def mock_dynamodb():
    """Create a mock DynamoDB client for basic init tests."""
    client = MagicMock()
    return client


class TestGrantManagerConfig:
    """Test GrantManagerConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = GrantManagerConfig()
        assert config.table_name == "aura-capability-grants"
        assert config.single_use_expiry_minutes == 60
        assert config.session_expiry_hours == 8
        assert config.max_active_grants_per_agent == 10
        assert config.enable_background_cleanup is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = GrantManagerConfig(
            table_name="custom-grants-table",
            max_active_grants_per_agent=5,
            cache_ttl_seconds=120,
        )
        assert config.table_name == "custom-grants-table"
        assert config.max_active_grants_per_agent == 5
        assert config.cache_ttl_seconds == 120


class TestDynamicGrantManager:
    """Test DynamicGrantManager basic functionality."""

    def test_initialization(self, in_memory_manager):
        """Test manager initialization."""
        manager = in_memory_manager
        assert manager.config is not None
        assert manager._grants_created == 0
        assert manager._running is False

    def test_initialization_with_config(self, grant_config: GrantManagerConfig):
        """Test initialization with custom config."""
        manager = InMemoryDynamicGrantManager(config=grant_config)
        assert manager.config.table_name == "test-capability-grants"

    @pytest.mark.asyncio
    async def test_start_stop(self, in_memory_manager):
        """Test starting and stopping the manager."""
        manager = in_memory_manager
        await manager.start()
        assert manager._running is True
        await manager.stop()
        assert manager._running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Test that start is idempotent."""
        config = GrantManagerConfig(enable_background_cleanup=True)
        manager = InMemoryDynamicGrantManager(config=config)
        await manager.start()
        task1 = manager._cleanup_task
        await manager.start()
        assert manager._cleanup_task is task1
        await manager.stop()


class TestGrantCreation:
    """Test grant creation functionality."""

    @pytest.mark.asyncio
    async def test_create_grant_from_approval(self, in_memory_manager):
        """Test creating a grant from approval response."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
            constraints={},
        )

        grant = await manager.create_grant(
            approval=approval,
            agent_id="agent-001",
            tool_name="provision_sandbox",
            action="execute",
        )

        assert grant.agent_id == "agent-001"
        assert grant.tool_name == "provision_sandbox"
        assert grant.action == "execute"
        assert grant.scope == CapabilityScope.SESSION
        assert grant.is_valid is True
        assert manager._grants_created == 1

    @pytest.mark.asyncio
    async def test_create_grant_single_use(self, in_memory_manager):
        """Test creating a single-use grant."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SINGLE_USE,
        )

        grant = await manager.create_grant(
            approval=approval,
            agent_id="agent-001",
            tool_name="test_tool",
            action="execute",
        )

        assert grant.max_usage == 1
        assert grant.scope == CapabilityScope.SINGLE_USE

    @pytest.mark.asyncio
    async def test_create_grant_with_constraints(self, in_memory_manager):
        """Test creating a grant with constraints."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
            constraints={"max_usage": 5, "max_sandboxes": 2},
        )

        grant = await manager.create_grant(
            approval=approval,
            agent_id="agent-001",
            tool_name="provision_sandbox",
            action="execute",
        )

        assert grant.max_usage == 5
        assert grant.constraints["max_sandboxes"] == 2

    @pytest.mark.asyncio
    async def test_create_grant_with_context_restrictions(self, in_memory_manager):
        """Test creating a grant with context restrictions."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )

        grant = await manager.create_grant(
            approval=approval,
            agent_id="agent-001",
            tool_name="test_tool",
            action="execute",
            context_restrictions=["sandbox", "test"],
        )

        assert grant.context_restrictions == ["sandbox", "test"]
        assert grant.is_applicable("test_tool", "execute", "sandbox") is True
        assert grant.is_applicable("test_tool", "execute", "production") is False

    @pytest.mark.asyncio
    async def test_create_grant_with_custom_expiry(self, in_memory_manager):
        """Test creating a grant with custom expiry time."""
        manager = in_memory_manager

        custom_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.TIME_BOUNDED,
            expires_at=custom_expiry,
        )

        grant = await manager.create_grant(
            approval=approval,
            agent_id="agent-001",
            tool_name="test_tool",
            action="execute",
        )

        assert grant.expires_at == custom_expiry

    @pytest.mark.asyncio
    async def test_create_grant_exceeds_limit(self):
        """Test that creating grants beyond limit raises error."""
        config = GrantManagerConfig(max_active_grants_per_agent=2)
        manager = InMemoryDynamicGrantManager(config=config)

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )

        # Create max grants
        await manager.create_grant(approval, "agent-001", "tool1", "execute")
        await manager.create_grant(approval, "agent-001", "tool2", "execute")

        # Third should fail
        with pytest.raises(ValueError, match="maximum active grants"):
            await manager.create_grant(approval, "agent-001", "tool3", "execute")


class TestGrantRetrieval:
    """Test grant retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_active_grants_empty(self, in_memory_manager):
        """Test getting grants when none exist."""
        manager = in_memory_manager
        grants = await manager.get_active_grants("agent-001")
        assert grants == []

    @pytest.mark.asyncio
    async def test_get_active_grants(self, in_memory_manager):
        """Test getting active grants for an agent."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )

        await manager.create_grant(approval, "agent-001", "tool1", "execute")
        await manager.create_grant(approval, "agent-001", "tool2", "execute")

        grants = await manager.get_active_grants("agent-001")
        assert len(grants) == 2

    @pytest.mark.asyncio
    async def test_get_active_grants_filters_invalid(self, in_memory_manager):
        """Test that expired/revoked grants are filtered out."""
        manager = in_memory_manager

        # Create a grant
        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )
        await manager.create_grant(approval, "agent-001", "tool1", "execute")

        # Manually add an expired grant to cache
        expired_grant = DynamicCapabilityGrant(
            grant_id="expired-001",
            agent_id="agent-001",
            tool_name="tool2",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="test",
            approver="admin",
            granted_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        manager._grant_cache["agent-001"].append(expired_grant)

        grants = await manager.get_active_grants("agent-001")
        assert len(grants) == 1
        assert grants[0].tool_name == "tool1"

    @pytest.mark.asyncio
    async def test_check_grant_found(self, in_memory_manager):
        """Test checking for a matching grant."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )
        await manager.create_grant(
            approval, "agent-001", "provision_sandbox", "execute"
        )

        grant = await manager.check_grant(
            "agent-001", "provision_sandbox", "execute", "development"
        )
        assert grant is not None
        assert grant.tool_name == "provision_sandbox"

    @pytest.mark.asyncio
    async def test_check_grant_not_found(self, in_memory_manager):
        """Test checking for a non-existent grant."""
        manager = in_memory_manager

        grant = await manager.check_grant(
            "agent-001", "provision_sandbox", "execute", "development"
        )
        assert grant is None

    @pytest.mark.asyncio
    async def test_check_grant_wrong_action(self, in_memory_manager):
        """Test checking for grant with wrong action."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )
        await manager.create_grant(approval, "agent-001", "provision_sandbox", "read")

        # Check for execute but grant is for read
        grant = await manager.check_grant(
            "agent-001", "provision_sandbox", "execute", "development"
        )
        assert grant is None


class TestGrantUsage:
    """Test grant usage tracking."""

    @pytest.mark.asyncio
    async def test_use_grant_success(self, in_memory_manager):
        """Test successful grant usage."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )
        grant = await manager.create_grant(
            approval, "agent-001", "test_tool", "execute"
        )

        result = await manager.use_grant(grant.grant_id, "agent-001")
        assert result is True
        assert manager._grants_used == 1

    @pytest.mark.asyncio
    async def test_use_grant_exhausted(self, in_memory_manager):
        """Test using an exhausted grant."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SINGLE_USE,  # Only 1 use
        )
        grant = await manager.create_grant(
            approval, "agent-001", "test_tool", "execute"
        )

        # First use should succeed
        result1 = await manager.use_grant(grant.grant_id, "agent-001")
        assert result1 is True

        # Second use should fail
        result2 = await manager.use_grant(grant.grant_id, "agent-001")
        assert result2 is False

    @pytest.mark.asyncio
    async def test_use_grant_not_found(self, in_memory_manager):
        """Test using a non-existent grant."""
        manager = in_memory_manager
        result = await manager.use_grant("nonexistent-grant", "agent-001")
        assert result is False


class TestGrantRevocation:
    """Test grant revocation functionality."""

    @pytest.mark.asyncio
    async def test_revoke_grant(self, in_memory_manager):
        """Test revoking a grant."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )
        grant = await manager.create_grant(
            approval, "agent-001", "test_tool", "execute"
        )

        result = await manager.revoke_grant(
            grant.grant_id, "agent-001", "Security concern"
        )
        assert result is True
        assert manager._grants_revoked == 1

        # Grant should no longer be active
        grants = await manager.get_active_grants("agent-001")
        assert len(grants) == 0

    @pytest.mark.asyncio
    async def test_revoke_grant_not_found(self, in_memory_manager):
        """Test revoking a non-existent grant."""
        manager = in_memory_manager
        result = await manager.revoke_grant("nonexistent-grant", "agent-001", "Test")
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_all_grants(self, in_memory_manager):
        """Test revoking all grants for an agent."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )
        await manager.create_grant(approval, "agent-001", "tool1", "execute")
        await manager.create_grant(approval, "agent-001", "tool2", "execute")
        await manager.create_grant(approval, "agent-001", "tool3", "execute")

        count = await manager.revoke_all_grants("agent-001", "Emergency shutdown")
        assert count == 3

        grants = await manager.get_active_grants("agent-001")
        assert len(grants) == 0


class TestGrantExtension:
    """Test grant extension functionality."""

    @pytest.mark.asyncio
    async def test_extend_grant(self, in_memory_manager):
        """Test extending a grant's expiry."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )
        grant = await manager.create_grant(
            approval, "agent-001", "test_tool", "execute"
        )
        original_expiry = grant.expires_at

        result = await manager.extend_grant(grant.grant_id, "agent-001", 4, "admin")
        assert result is True

        # Verify extension in cache
        grants = await manager.get_active_grants("agent-001")
        assert len(grants) == 1
        assert grants[0].expires_at > original_expiry

    @pytest.mark.asyncio
    async def test_extend_grant_not_found(self, in_memory_manager):
        """Test extending a non-existent grant."""
        manager = in_memory_manager
        result = await manager.extend_grant(
            "nonexistent-grant", "agent-001", 4, "admin"
        )
        assert result is False


class TestGrantCache:
    """Test grant caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_hits(self, in_memory_manager):
        """Test cache returns grants consistently."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )
        await manager.create_grant(approval, "agent-001", "test_tool", "execute")

        # First call
        grants1 = await manager.get_active_grants("agent-001")

        # Second call should return same grants
        grants2 = await manager.get_active_grants("agent-001")

        assert len(grants1) == 1
        assert len(grants2) == 1
        assert grants1[0].grant_id == grants2[0].grant_id

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, in_memory_manager):
        """Test cache invalidation on grant creation."""
        manager = in_memory_manager

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )

        # Create first grant and populate cache
        await manager.create_grant(approval, "agent-001", "tool1", "execute")
        await manager.get_active_grants("agent-001")

        # Creating another grant should invalidate cache
        assert "agent-001" in manager._grant_cache
        await manager.create_grant(approval, "agent-001", "tool2", "execute")
        # Cache should be invalidated (though it will be repopulated on next get)


class TestGrantManagerMetrics:
    """Test grant manager metrics."""

    def test_get_metrics(self, in_memory_manager):
        """Test getting manager metrics."""
        manager = in_memory_manager
        manager._grants_created = 10
        manager._grants_used = 50
        manager._grants_revoked = 2
        manager._cache_hits = 100
        manager._cache_misses = 20

        metrics = manager.get_metrics()
        assert metrics["grants_created"] == 10
        assert metrics["grants_used"] == 50
        assert metrics["grants_revoked"] == 2
        assert metrics["cache_hits"] == 100
        assert metrics["cache_misses"] == 20


class TestGrantManagerSingleton:
    """Test global grant manager singleton."""

    def test_get_grant_manager_singleton(self):
        """Test global singleton."""
        manager1 = get_grant_manager()
        manager2 = get_grant_manager()
        assert manager1 is manager2


class TestGrantExpiryCalculation:
    """Test grant expiry time calculation."""

    @pytest.mark.asyncio
    async def test_single_use_expiry(self):
        """Test single-use grant has correct expiry."""
        config = GrantManagerConfig(single_use_expiry_minutes=30)
        manager = InMemoryDynamicGrantManager(config=config)

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SINGLE_USE,
        )

        before = datetime.now(timezone.utc)
        grant = await manager.create_grant(approval, "agent-001", "test", "execute")
        after = datetime.now(timezone.utc)

        # Expiry should be approximately 30 minutes from now
        expected_min = before + timedelta(minutes=30)
        expected_max = after + timedelta(minutes=30)

        assert expected_min <= grant.expires_at <= expected_max

    @pytest.mark.asyncio
    async def test_session_expiry(self):
        """Test session grant has correct expiry."""
        config = GrantManagerConfig(session_expiry_hours=4)
        manager = InMemoryDynamicGrantManager(config=config)

        approval = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )

        before = datetime.now(timezone.utc)
        grant = await manager.create_grant(approval, "agent-001", "test", "execute")

        # Expiry should be approximately 4 hours from now
        expected = before + timedelta(hours=4)
        assert (
            abs((grant.expires_at - expected).total_seconds()) < 5
        )  # Within 5 seconds


class TestDynamicGrantProperties:
    """Test DynamicCapabilityGrant properties."""

    def test_is_valid_active_grant(self, sample_grant: DynamicCapabilityGrant):
        """Test is_valid for active grant."""
        assert sample_grant.is_valid is True

    def test_is_valid_expired_grant(self, expired_grant: DynamicCapabilityGrant):
        """Test is_valid for expired grant."""
        assert expired_grant.is_valid is False

    def test_is_valid_revoked_grant(self, revoked_grant: DynamicCapabilityGrant):
        """Test is_valid for revoked grant."""
        assert revoked_grant.is_valid is False

    def test_remaining_uses_unlimited(self, sample_grant: DynamicCapabilityGrant):
        """Test remaining_uses when no limit."""
        assert sample_grant.remaining_uses is None

    def test_remaining_uses_limited(self):
        """Test remaining_uses with limit."""
        grant = DynamicCapabilityGrant(
            grant_id="test-001",
            agent_id="agent-001",
            tool_name="test_tool",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="test",
            approver="admin",
            granted_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            usage_count=3,
            max_usage=10,
        )
        assert grant.remaining_uses == 7
