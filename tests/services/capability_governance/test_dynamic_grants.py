"""
Tests for capability governance dynamic grants module.

Tests grant creation, validation, usage tracking, and expiration.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.capability_governance.contracts import (
    CapabilityApprovalResponse,
    CapabilityScope,
)
from src.services.capability_governance.dynamic_grants import (
    DynamicGrantManager,
    GrantManagerConfig,
    get_grant_manager,
    reset_grant_manager,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def cleanup():
    """Reset singletons after each test."""
    yield
    reset_grant_manager()


@pytest.fixture
def grant_config():
    """Create test grant configuration."""
    return GrantManagerConfig(
        table_name="test-capability-grants",
        enable_background_cleanup=False,
    )


@pytest.fixture
def grant_manager(grant_config, mock_dynamodb):
    """Create grant manager with test config and mock DynamoDB."""
    return DynamicGrantManager(config=grant_config, dynamodb_client=mock_dynamodb)


class MockConditionalCheckFailed(Exception):
    """Mock exception for conditional check failures."""


@pytest.fixture
def mock_dynamodb():
    """Create stateful mock DynamoDB client that tracks grants."""
    mock = MagicMock()

    # In-memory storage for the mock
    storage = {}

    # Create mock exceptions attribute
    mock.exceptions = MagicMock()
    mock.exceptions.ConditionalCheckFailedException = MockConditionalCheckFailed

    def put_item(**kwargs):
        """Store item in mock storage."""
        table = kwargs.get("TableName", "default")
        item = kwargs.get("Item", {})
        pk = item.get("PK", {}).get("S", "")
        sk = item.get("SK", {}).get("S", "")
        key = f"{table}:{pk}:{sk}"
        storage[key] = item
        return {}

    def query(**kwargs):
        """Query items from mock storage."""
        table = kwargs.get("TableName", "default")
        pk_value = (
            kwargs.get("ExpressionAttributeValues", {}).get(":pk", {}).get("S", "")
        )
        filter_grant_id = (
            kwargs.get("ExpressionAttributeValues", {})
            .get(":grant_id", {})
            .get("S", "")
        )
        items = []
        for key, item in storage.items():
            if key.startswith(f"{table}:{pk_value}:"):
                # Only return non-revoked items
                if not item.get("revoked", {}).get("BOOL", False):
                    # If filter by grant_id is specified, apply it
                    if filter_grant_id:
                        if item.get("grant_id", {}).get("S", "") == filter_grant_id:
                            items.append(item)
                    else:
                        items.append(item)
        return {"Items": items}

    def update_item(**kwargs):
        """Update item in mock storage with conditional check."""
        table = kwargs.get("TableName", "default")
        pk = kwargs.get("Key", {}).get("PK", {}).get("S", "")
        sk = kwargs.get("Key", {}).get("SK", {}).get("S", "")
        key = f"{table}:{pk}:{sk}"

        if key in storage:
            item = storage[key]
            update_expr = kwargs.get("UpdateExpression", "")
            condition_expr = kwargs.get("ConditionExpression", "")
            attr_values = kwargs.get("ExpressionAttributeValues", {})

            # Check for usage increment with max_usage condition
            if "usage_count = usage_count + :inc" in update_expr:
                current_usage = int(item.get("usage_count", {}).get("N", "0"))
                max_usage = item.get("max_usage", {}).get("N")

                # Check condition: attribute_not_exists(max_usage) OR usage_count < max_usage
                if max_usage is not None:
                    max_usage_int = int(max_usage)
                    if current_usage >= max_usage_int:
                        # Raise conditional check failure
                        raise MockConditionalCheckFailed("Conditional check failed")

                # Increment usage count
                new_usage = current_usage + 1
                item["usage_count"] = {"N": str(new_usage)}
                return {"Attributes": {"usage_count": {"N": str(new_usage)}}}

            # Handle revocation updates
            if ":revoked" in attr_values:
                item["revoked"] = attr_values[":revoked"]

        return {"Attributes": {"usage_count": {"N": "1"}}}

    def delete_item(**kwargs):
        """Delete item from mock storage."""
        table = kwargs.get("TableName", "default")
        pk = kwargs.get("Key", {}).get("PK", {}).get("S", "")
        sk = kwargs.get("Key", {}).get("SK", {}).get("S", "")
        key = f"{table}:{pk}:{sk}"
        if key in storage:
            del storage[key]
        return {}

    mock.put_item = MagicMock(side_effect=put_item)
    mock.query = MagicMock(side_effect=query)
    mock.update_item = MagicMock(side_effect=update_item)
    mock.delete_item = MagicMock(side_effect=delete_item)

    return mock


@pytest.fixture
def approval_response():
    """Create a sample approval response."""
    return CapabilityApprovalResponse(
        request_id="req-123",
        approved=True,
        approver_id="admin-456",
        scope=CapabilityScope.SESSION,
        constraints={},
        reason="Approved for testing",
    )


# =============================================================================
# GrantManagerConfig Tests
# =============================================================================


class TestGrantManagerConfig:
    """Tests for GrantManagerConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = GrantManagerConfig()
        assert config.table_name == "aura-capability-grants"
        assert config.single_use_expiry_minutes == 60
        assert config.session_expiry_hours == 8
        assert config.max_active_grants_per_agent == 10

    def test_custom_values(self):
        """Test custom configuration values."""
        config = GrantManagerConfig(
            table_name="custom-grants",
            single_use_expiry_minutes=30,
            max_active_grants_per_agent=5,
        )
        assert config.table_name == "custom-grants"
        assert config.single_use_expiry_minutes == 30
        assert config.max_active_grants_per_agent == 5


# =============================================================================
# DynamicGrantManager Basic Tests
# =============================================================================


class TestDynamicGrantManagerBasic:
    """Basic tests for DynamicGrantManager."""

    def test_initialization(self, grant_manager):
        """Test manager initialization."""
        assert grant_manager is not None
        assert grant_manager.config is not None

    @pytest.mark.asyncio
    async def test_create_grant(self, grant_manager, approval_response):
        """Test creating a grant."""
        grant = await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="deploy_to_production",
            action="execute",
        )

        assert grant.grant_id is not None
        assert grant.agent_id == "agent-123"
        assert grant.tool_name == "deploy_to_production"
        assert grant.scope == CapabilityScope.SESSION
        assert grant.is_valid is True

    @pytest.mark.asyncio
    async def test_create_grant_single_use(self, grant_manager):
        """Test creating a single-use grant."""
        approval = CapabilityApprovalResponse(
            request_id="req-123",
            approved=True,
            approver_id="admin-456",
            scope=CapabilityScope.SINGLE_USE,
        )

        grant = await grant_manager.create_grant(
            approval=approval,
            agent_id="agent-123",
            tool_name="critical_tool",
            action="execute",
        )

        assert grant.scope == CapabilityScope.SINGLE_USE
        assert grant.max_usage == 1

    @pytest.mark.asyncio
    async def test_create_grant_with_context_restrictions(
        self, grant_manager, approval_response
    ):
        """Test creating a grant with context restrictions."""
        grant = await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="deploy_to_production",
            action="execute",
            context_restrictions=["staging", "sandbox"],
        )

        assert "staging" in grant.context_restrictions
        assert "sandbox" in grant.context_restrictions

    @pytest.mark.asyncio
    async def test_create_grant_max_active_limit(
        self, grant_manager, approval_response
    ):
        """Test that max active grants limit is enforced."""
        # Create max grants
        for i in range(grant_manager.config.max_active_grants_per_agent):
            await grant_manager.create_grant(
                approval=approval_response,
                agent_id="agent-limit-test",
                tool_name=f"tool_{i}",
                action="execute",
            )

        # Try to create one more
        with pytest.raises(ValueError) as exc_info:
            await grant_manager.create_grant(
                approval=approval_response,
                agent_id="agent-limit-test",
                tool_name="tool_extra",
                action="execute",
            )

        assert "maximum active grants" in str(exc_info.value)


# =============================================================================
# Grant Lookup Tests
# =============================================================================


class TestGrantLookup:
    """Tests for grant lookup."""

    @pytest.mark.asyncio
    async def test_get_active_grants(self, grant_manager, approval_response):
        """Test getting active grants for an agent."""
        # Create some grants
        await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="tool_1",
            action="execute",
        )
        await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="tool_2",
            action="execute",
        )

        grants = await grant_manager.get_active_grants("agent-123")

        assert len(grants) == 2

    @pytest.mark.asyncio
    async def test_get_active_grants_empty(self, grant_manager):
        """Test getting active grants when none exist."""
        grants = await grant_manager.get_active_grants("nonexistent-agent")
        assert len(grants) == 0

    @pytest.mark.asyncio
    async def test_check_grant_found(self, grant_manager, approval_response):
        """Test checking for a matching grant."""
        await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="deploy_to_production",
            action="execute",
        )

        grant = await grant_manager.check_grant(
            agent_id="agent-123",
            tool_name="deploy_to_production",
            action="execute",
            context="sandbox",
        )

        assert grant is not None
        assert grant.tool_name == "deploy_to_production"

    @pytest.mark.asyncio
    async def test_check_grant_not_found(self, grant_manager):
        """Test checking for a non-existent grant."""
        grant = await grant_manager.check_grant(
            agent_id="agent-123",
            tool_name="nonexistent_tool",
            action="execute",
            context="sandbox",
        )

        assert grant is None


# =============================================================================
# Grant Usage Tests
# =============================================================================


class TestGrantUsage:
    """Tests for grant usage tracking."""

    @pytest.mark.asyncio
    async def test_use_grant(self, grant_manager, approval_response):
        """Test recording grant usage."""
        grant = await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="deploy_to_production",
            action="execute",
        )

        result = await grant_manager.use_grant(grant.grant_id, "agent-123")

        assert result is True

    @pytest.mark.asyncio
    async def test_use_grant_exhausted(self, grant_manager):
        """Test using an exhausted grant."""
        # Create single-use grant
        approval = CapabilityApprovalResponse(
            request_id="req-123",
            approved=True,
            approver_id="admin-456",
            scope=CapabilityScope.SINGLE_USE,
        )

        grant = await grant_manager.create_grant(
            approval=approval,
            agent_id="agent-123",
            tool_name="critical_tool",
            action="execute",
        )

        # Use once
        result1 = await grant_manager.use_grant(grant.grant_id, "agent-123")
        assert result1 is True

        # Try to use again - should fail
        result2 = await grant_manager.use_grant(grant.grant_id, "agent-123")
        assert result2 is False


# =============================================================================
# Grant Revocation Tests
# =============================================================================


class TestGrantRevocation:
    """Tests for grant revocation."""

    @pytest.mark.asyncio
    async def test_revoke_grant(self, grant_manager, approval_response):
        """Test revoking a grant."""
        grant = await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="deploy_to_production",
            action="execute",
        )

        result = await grant_manager.revoke_grant(
            grant_id=grant.grant_id,
            agent_id="agent-123",
            reason="No longer needed",
            revoked_by="admin",
        )

        assert result is True

        # Verify grant is no longer valid
        grants = await grant_manager.get_active_grants("agent-123")
        assert len(grants) == 0

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_grant(self, grant_manager):
        """Test revoking a non-existent grant."""
        result = await grant_manager.revoke_grant(
            grant_id="nonexistent-grant",
            agent_id="agent-123",
            reason="Test",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_all_grants(self, grant_manager, approval_response):
        """Test revoking all grants for an agent."""
        # Create multiple grants
        await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="tool_1",
            action="execute",
        )
        await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="tool_2",
            action="execute",
        )

        count = await grant_manager.revoke_all_grants(
            agent_id="agent-123",
            reason="Security incident",
            revoked_by="security",
        )

        assert count == 2

        # Verify no grants remain
        grants = await grant_manager.get_active_grants("agent-123")
        assert len(grants) == 0


# =============================================================================
# Grant Extension Tests
# =============================================================================


class TestGrantExtension:
    """Tests for grant extension."""

    @pytest.mark.asyncio
    async def test_extend_grant(self, grant_manager, approval_response):
        """Test extending a grant."""
        grant = await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="deploy_to_production",
            action="execute",
        )

        original_expiry = grant.expires_at

        result = await grant_manager.extend_grant(
            grant_id=grant.grant_id,
            agent_id="agent-123",
            extension_hours=4,
            extended_by="admin",
        )

        assert result is True


# =============================================================================
# Expiry Calculation Tests
# =============================================================================


class TestExpiryCalculation:
    """Tests for grant expiry calculation."""

    def test_calculate_expiry_single_use(self, grant_manager):
        """Test expiry calculation for single-use scope."""
        expiry = grant_manager._calculate_expiry(CapabilityScope.SINGLE_USE)
        expected_min = datetime.now(timezone.utc) + timedelta(minutes=55)
        expected_max = datetime.now(timezone.utc) + timedelta(minutes=65)

        assert expected_min < expiry < expected_max

    def test_calculate_expiry_session(self, grant_manager):
        """Test expiry calculation for session scope."""
        expiry = grant_manager._calculate_expiry(CapabilityScope.SESSION)
        expected_min = datetime.now(timezone.utc) + timedelta(hours=7)
        expected_max = datetime.now(timezone.utc) + timedelta(hours=9)

        assert expected_min < expiry < expected_max

    def test_calculate_expiry_task_tree(self, grant_manager):
        """Test expiry calculation for task tree scope."""
        expiry = grant_manager._calculate_expiry(CapabilityScope.TASK_TREE)
        expected_min = datetime.now(timezone.utc) + timedelta(hours=23)
        expected_max = datetime.now(timezone.utc) + timedelta(hours=25)

        assert expected_min < expiry < expected_max


# =============================================================================
# Metrics Tests
# =============================================================================


class TestGrantMetrics:
    """Tests for grant manager metrics."""

    @pytest.mark.asyncio
    async def test_get_metrics(self, grant_manager, approval_response):
        """Test getting grant manager metrics."""
        # Create and use some grants
        grant = await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="deploy_to_production",
            action="execute",
        )
        await grant_manager.use_grant(grant.grant_id, "agent-123")

        metrics = grant_manager.get_metrics()

        assert "grants_created" in metrics
        assert metrics["grants_created"] >= 1
        assert "grants_used" in metrics
        assert metrics["grants_used"] >= 1


# =============================================================================
# Caching Tests
# =============================================================================


class TestGrantCaching:
    """Tests for grant caching."""

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_create(self, grant_manager, approval_response):
        """Test that cache is invalidated when grant is created."""
        # Pre-populate cache
        await grant_manager.get_active_grants("agent-123")

        # Create grant should invalidate cache
        await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="deploy_to_production",
            action="execute",
        )

        # Cache should be invalid
        assert "agent-123" not in grant_manager._grant_cache

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_revoke(self, grant_manager, approval_response):
        """Test that cache is invalidated when grant is revoked."""
        grant = await grant_manager.create_grant(
            approval=approval_response,
            agent_id="agent-123",
            tool_name="deploy_to_production",
            action="execute",
        )

        # Populate cache
        await grant_manager.get_active_grants("agent-123")

        # Revoke should invalidate cache
        await grant_manager.revoke_grant(grant.grant_id, "agent-123", "Test")

        assert "agent-123" not in grant_manager._grant_cache


# =============================================================================
# Singleton Tests
# =============================================================================


class TestGrantSingleton:
    """Tests for grant manager singleton."""

    def test_get_grant_manager(self):
        """Test getting global grant manager."""
        reset_grant_manager()
        m1 = get_grant_manager()
        m2 = get_grant_manager()
        assert m1 is m2

    def test_reset_grant_manager(self):
        """Test resetting global grant manager."""
        m1 = get_grant_manager()
        reset_grant_manager()
        m2 = get_grant_manager()
        assert m1 is not m2


# =============================================================================
# Background Cleanup Tests
# =============================================================================


class TestBackgroundCleanup:
    """Tests for background cleanup task."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the manager."""
        config = GrantManagerConfig(enable_background_cleanup=True)
        manager = DynamicGrantManager(config=config)

        await manager.start()
        assert manager._running is True

        await manager.stop()
        assert manager._running is False
