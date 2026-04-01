"""
Tests for Project Aura - A2A Agent Registry

Comprehensive tests for agent registration, discovery, health monitoring,
and capability matching per ADR-028 Phase 6.
"""

import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# Module Isolation: Save and restore src.config to prevent test pollution
# =============================================================================

# Save original modules before mocking
_original_src_config = sys.modules.get("src.config")
_original_a2a_gateway = sys.modules.get("src.services.a2a_gateway")

# Mock config module before importing
mock_config = MagicMock()
mock_config.IntegrationConfig = MagicMock
mock_config.get_integration_config = MagicMock(
    return_value=MagicMock(is_defense_mode=False)
)


# Create require_enterprise_mode decorator that just passes through
def require_enterprise_mode(func):
    """Mock decorator that just passes through."""
    return func


mock_config.require_enterprise_mode = require_enterprise_mode
sys.modules["src.config"] = mock_config

# Mock a2a_gateway module
mock_gateway = MagicMock()


class MockAgentCapability:
    """Mock AgentCapability class."""

    def __init__(self, name: str = "test_capability", description: str = "Test"):
        self.name = name
        self.description = description


class MockAgentCard:
    """Mock AgentCard class."""

    def __init__(
        self,
        agent_id: str = "test-agent-1",
        endpoint: str = "https://agent.example.com",
        provider: str = "TestProvider",
        capabilities: list = None,
    ):
        self.agent_id = agent_id
        self.endpoint = endpoint
        self.provider = provider
        self.capabilities = capabilities or [MockAgentCapability()]

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "endpoint": self.endpoint,
            "provider": self.provider,
            "capabilities": [
                {"name": c.name, "description": c.description}
                for c in self.capabilities
            ],
        }


mock_gateway.AgentCard = MockAgentCard
mock_gateway.AgentCapability = MockAgentCapability
sys.modules["src.services.a2a_gateway"] = mock_gateway

# Now import the module under test
from src.services.a2a_agent_registry import (
    A2AAgentRegistry,
    AgentAlreadyExistsError,
    AgentNotFoundError,
    AgentSearchCriteria,
    AgentStatus,
    AgentTrustLevel,
    RegisteredAgent,
    RegistrationError,
    RegistryError,
)

# Restore original modules to prevent pollution of other test files
if _original_src_config is not None:
    sys.modules["src.config"] = _original_src_config
else:
    sys.modules.pop("src.config", None)

if _original_a2a_gateway is not None:
    sys.modules["src.services.a2a_gateway"] = _original_a2a_gateway
else:
    sys.modules.pop("src.services.a2a_gateway", None)


# =============================================================================
# AgentStatus Enum Tests
# =============================================================================


class TestAgentStatus:
    """Tests for AgentStatus enum."""

    def test_active(self):
        """Test ACTIVE status."""
        assert AgentStatus.ACTIVE.value == "active"

    def test_degraded(self):
        """Test DEGRADED status."""
        assert AgentStatus.DEGRADED.value == "degraded"

    def test_inactive(self):
        """Test INACTIVE status."""
        assert AgentStatus.INACTIVE.value == "inactive"

    def test_suspended(self):
        """Test SUSPENDED status."""
        assert AgentStatus.SUSPENDED.value == "suspended"

    def test_pending(self):
        """Test PENDING status."""
        assert AgentStatus.PENDING.value == "pending"

    def test_all_statuses_exist(self):
        """Test all expected statuses are defined."""
        expected = {"active", "degraded", "inactive", "suspended", "pending"}
        actual = {s.value for s in AgentStatus}
        assert actual == expected


# =============================================================================
# AgentTrustLevel Enum Tests
# =============================================================================


class TestAgentTrustLevel:
    """Tests for AgentTrustLevel enum."""

    def test_verified(self):
        """Test VERIFIED trust level."""
        assert AgentTrustLevel.VERIFIED.value == "verified"

    def test_trusted(self):
        """Test TRUSTED trust level."""
        assert AgentTrustLevel.TRUSTED.value == "trusted"

    def test_standard(self):
        """Test STANDARD trust level."""
        assert AgentTrustLevel.STANDARD.value == "standard"

    def test_untrusted(self):
        """Test UNTRUSTED trust level."""
        assert AgentTrustLevel.UNTRUSTED.value == "untrusted"

    def test_all_trust_levels_exist(self):
        """Test all expected trust levels are defined."""
        expected = {"verified", "trusted", "standard", "untrusted"}
        actual = {t.value for t in AgentTrustLevel}
        assert actual == expected


# =============================================================================
# RegisteredAgent Tests
# =============================================================================


class TestRegisteredAgent:
    """Tests for RegisteredAgent dataclass."""

    def test_default_creation(self):
        """Test creating RegisteredAgent with defaults."""
        card = MockAgentCard()
        agent = RegisteredAgent(agent_card=card)

        assert agent.agent_card == card
        assert agent.registration_id == ""
        assert agent.registered_by == "system"
        assert agent.status == AgentStatus.PENDING
        assert agent.trust_level == AgentTrustLevel.STANDARD
        assert agent.health_check_failures == 0
        assert agent.average_latency_ms == 0.0

    def test_custom_creation(self):
        """Test creating RegisteredAgent with custom values."""
        card = MockAgentCard(agent_id="custom-agent")
        agent = RegisteredAgent(
            agent_card=card,
            registration_id="reg-123",
            registered_by="admin",
            status=AgentStatus.ACTIVE,
            trust_level=AgentTrustLevel.VERIFIED,
            tags=["production", "high-priority"],
        )

        assert agent.registration_id == "reg-123"
        assert agent.registered_by == "admin"
        assert agent.status == AgentStatus.ACTIVE
        assert agent.trust_level == AgentTrustLevel.VERIFIED
        assert "production" in agent.tags

    def test_agent_id_property(self):
        """Test agent_id property returns from card."""
        card = MockAgentCard(agent_id="my-agent")
        agent = RegisteredAgent(agent_card=card)
        assert agent.agent_id == "my-agent"

    def test_endpoint_property(self):
        """Test endpoint property returns from card."""
        card = MockAgentCard(endpoint="https://test.example.com")
        agent = RegisteredAgent(agent_card=card)
        assert agent.endpoint == "https://test.example.com"

    def test_capabilities_property(self):
        """Test capabilities property returns from card."""
        caps = [MockAgentCapability("cap1"), MockAgentCapability("cap2")]
        card = MockAgentCard(capabilities=caps)
        agent = RegisteredAgent(agent_card=card)
        assert len(agent.capabilities) == 2

    def test_success_rate_no_tasks(self):
        """Test success rate with no tasks completed."""
        card = MockAgentCard()
        agent = RegisteredAgent(agent_card=card)
        assert agent.success_rate == 1.0

    def test_success_rate_with_tasks(self):
        """Test success rate calculation."""
        card = MockAgentCard()
        agent = RegisteredAgent(
            agent_card=card,
            total_tasks_completed=8,
            total_tasks_failed=2,
        )
        assert agent.success_rate == 0.8

    def test_success_rate_all_failed(self):
        """Test success rate with all failures."""
        card = MockAgentCard()
        agent = RegisteredAgent(
            agent_card=card,
            total_tasks_completed=0,
            total_tasks_failed=10,
        )
        assert agent.success_rate == 0.0

    def test_is_healthy_active(self):
        """Test is_healthy for active agent."""
        card = MockAgentCard()
        agent = RegisteredAgent(
            agent_card=card,
            status=AgentStatus.ACTIVE,
            health_check_failures=0,
        )
        assert agent.is_healthy is True

    def test_is_healthy_too_many_failures(self):
        """Test is_healthy with too many failures."""
        card = MockAgentCard()
        agent = RegisteredAgent(
            agent_card=card,
            status=AgentStatus.ACTIVE,
            health_check_failures=3,
        )
        assert agent.is_healthy is False

    def test_is_healthy_not_active(self):
        """Test is_healthy when not active."""
        card = MockAgentCard()
        agent = RegisteredAgent(
            agent_card=card,
            status=AgentStatus.DEGRADED,
            health_check_failures=0,
        )
        assert agent.is_healthy is False

    def test_is_rate_limited_false(self):
        """Test rate limiting when under limit."""
        card = MockAgentCard()
        agent = RegisteredAgent(
            agent_card=card,
            rate_limit_per_minute=100,
            current_minute_requests=50,
        )
        assert agent.is_rate_limited() is False

    def test_is_rate_limited_true(self):
        """Test rate limiting when at limit."""
        card = MockAgentCard()
        agent = RegisteredAgent(
            agent_card=card,
            rate_limit_per_minute=100,
            current_minute_requests=100,
        )
        assert agent.is_rate_limited() is True

    def test_is_rate_limited_resets_after_minute(self):
        """Test rate limit reset after 60 seconds."""
        card = MockAgentCard()
        agent = RegisteredAgent(
            agent_card=card,
            rate_limit_per_minute=100,
            current_minute_requests=100,
            last_rate_reset=time.time() - 61,  # Over a minute ago
        )
        # Should reset and return False
        assert agent.is_rate_limited() is False
        assert agent.current_minute_requests == 0

    def test_record_request_allowed(self):
        """Test recording a request when allowed."""
        card = MockAgentCard()
        agent = RegisteredAgent(
            agent_card=card,
            rate_limit_per_minute=100,
            current_minute_requests=0,
        )
        result = agent.record_request()
        assert result is True
        assert agent.current_minute_requests == 1

    def test_record_request_rate_limited(self):
        """Test recording a request when rate limited."""
        card = MockAgentCard()
        agent = RegisteredAgent(
            agent_card=card,
            rate_limit_per_minute=100,
            current_minute_requests=100,
        )
        result = agent.record_request()
        assert result is False

    def test_record_task_completion_success(self):
        """Test recording successful task completion."""
        card = MockAgentCard()
        agent = RegisteredAgent(agent_card=card)

        agent.record_task_completion(success=True, latency_ms=100.0)

        assert agent.total_tasks_sent == 1
        assert agent.total_tasks_completed == 1
        assert agent.total_tasks_failed == 0
        assert agent.average_latency_ms == 100.0

    def test_record_task_completion_failure(self):
        """Test recording failed task completion."""
        card = MockAgentCard()
        agent = RegisteredAgent(agent_card=card)

        agent.record_task_completion(success=False, latency_ms=5000.0)

        assert agent.total_tasks_sent == 1
        assert agent.total_tasks_completed == 0
        assert agent.total_tasks_failed == 1

    def test_record_task_completion_average_latency(self):
        """Test average latency calculation."""
        card = MockAgentCard()
        agent = RegisteredAgent(agent_card=card)

        agent.record_task_completion(success=True, latency_ms=100.0)
        agent.record_task_completion(success=True, latency_ms=200.0)

        assert agent.average_latency_ms == 150.0

    def test_to_dict(self):
        """Test to_dict serialization."""
        card = MockAgentCard(agent_id="test-agent")
        agent = RegisteredAgent(
            agent_card=card,
            registration_id="reg-test",
            status=AgentStatus.ACTIVE,
            trust_level=AgentTrustLevel.TRUSTED,
            tags=["test"],
        )

        result = agent.to_dict()

        assert result["registration_id"] == "reg-test"
        assert result["status"] == "active"
        assert result["trust_level"] == "trusted"
        assert "agent" in result
        assert result["tags"] == ["test"]


# =============================================================================
# AgentSearchCriteria Tests
# =============================================================================


class TestAgentSearchCriteria:
    """Tests for AgentSearchCriteria dataclass."""

    def test_default_criteria(self):
        """Test default search criteria."""
        criteria = AgentSearchCriteria()

        assert criteria.capability_name is None
        assert criteria.provider is None
        assert criteria.status is None
        assert criteria.trust_level is None
        assert criteria.min_success_rate == 0.0
        assert criteria.max_latency_ms is None
        assert criteria.tags == []
        assert criteria.limit == 10
        assert criteria.offset == 0

    def test_custom_criteria(self):
        """Test custom search criteria."""
        criteria = AgentSearchCriteria(
            capability_name="code_review",
            provider="anthropic",
            status=AgentStatus.ACTIVE,
            trust_level=AgentTrustLevel.VERIFIED,
            min_success_rate=0.95,
            max_latency_ms=1000.0,
            tags=["production"],
            limit=50,
            offset=10,
        )

        assert criteria.capability_name == "code_review"
        assert criteria.provider == "anthropic"
        assert criteria.status == AgentStatus.ACTIVE
        assert criteria.trust_level == AgentTrustLevel.VERIFIED
        assert criteria.min_success_rate == 0.95
        assert criteria.max_latency_ms == 1000.0
        assert "production" in criteria.tags


# =============================================================================
# A2AAgentRegistry Tests
# =============================================================================


class TestA2AAgentRegistryInit:
    """Tests for A2AAgentRegistry initialization."""

    def test_init_enterprise_mode(self):
        """Test initialization in enterprise mode."""
        registry = A2AAgentRegistry()
        assert registry._agents == {}
        assert registry._capability_index == {}
        assert registry._provider_index == {}

    def test_init_custom_health_check_interval(self):
        """Test initialization with custom health check interval."""
        registry = A2AAgentRegistry(health_check_interval=120.0)
        assert registry._health_check_interval == 120.0

    def test_init_defense_mode_fails(self):
        """Test initialization fails in defense mode."""
        defense_config = MagicMock(is_defense_mode=True)
        with pytest.raises(RuntimeError) as exc_info:
            A2AAgentRegistry(config=defense_config)
        assert "DEFENSE mode" in str(exc_info.value)


class TestA2AAgentRegistryRegistration:
    """Tests for agent registration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = A2AAgentRegistry()

    @pytest.mark.asyncio
    async def test_register_new_agent(self):
        """Test registering a new agent."""
        card = MockAgentCard(agent_id="new-agent")
        result = await self.registry.register_agent(card, verify=False)

        assert result.agent_id == "new-agent"
        assert result.status == AgentStatus.ACTIVE
        assert "new-agent" in self.registry._agents

    @pytest.mark.asyncio
    async def test_register_agent_with_tags(self):
        """Test registering agent with tags."""
        card = MockAgentCard(agent_id="tagged-agent")
        result = await self.registry.register_agent(
            card, tags=["production", "critical"], verify=False
        )

        assert "production" in result.tags
        assert "critical" in result.tags

    @pytest.mark.asyncio
    async def test_register_agent_already_exists(self):
        """Test re-registering an existing agent updates it."""
        card1 = MockAgentCard(agent_id="existing-agent")
        await self.registry.register_agent(card1, verify=False)

        card2 = MockAgentCard(
            agent_id="existing-agent", endpoint="https://new.endpoint.com"
        )
        result = await self.registry.register_agent(card2, verify=False)

        # Should update existing
        assert result.endpoint == "https://new.endpoint.com"

    @pytest.mark.asyncio
    async def test_register_agent_aenealabs_verified(self):
        """Test aenealabs agents get VERIFIED trust level."""
        card = MockAgentCard(agent_id="aenea-agent", provider="aenealabs")
        result = await self.registry.register_agent(card, verify=False)

        assert result.trust_level == AgentTrustLevel.VERIFIED

    @pytest.mark.asyncio
    async def test_register_agent_trusted_provider(self):
        """Test trusted providers get TRUSTED level."""
        card = MockAgentCard(agent_id="anthropic-agent", provider="anthropic")
        result = await self.registry.register_agent(card, verify=False)

        assert result.trust_level == AgentTrustLevel.TRUSTED

    @pytest.mark.asyncio
    async def test_register_agent_standard_provider(self):
        """Test unknown providers get STANDARD level."""
        card = MockAgentCard(agent_id="unknown-agent", provider="unknown_provider")
        result = await self.registry.register_agent(card, verify=False)

        assert result.trust_level == AgentTrustLevel.STANDARD

    @pytest.mark.asyncio
    async def test_register_agent_updates_indexes(self):
        """Test that registration updates capability and provider indexes."""
        caps = [MockAgentCapability("code_review"), MockAgentCapability("testing")]
        card = MockAgentCard(
            agent_id="indexed-agent", provider="TestProvider", capabilities=caps
        )
        await self.registry.register_agent(card, verify=False)

        assert "indexed-agent" in self.registry._capability_index.get(
            "code_review", set()
        )
        assert "indexed-agent" in self.registry._capability_index.get("testing", set())
        assert "indexed-agent" in self.registry._provider_index.get(
            "TestProvider", set()
        )

    @pytest.mark.asyncio
    async def test_unregister_agent(self):
        """Test unregistering an agent."""
        card = MockAgentCard(agent_id="to-remove")
        await self.registry.register_agent(card, verify=False)

        result = await self.registry.unregister_agent("to-remove")

        assert result is True
        assert "to-remove" not in self.registry._agents

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_agent(self):
        """Test unregistering an agent that doesn't exist."""
        result = await self.registry.unregister_agent("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_agent_status(self):
        """Test updating an agent's status."""
        card = MockAgentCard(agent_id="status-agent")
        await self.registry.register_agent(card, verify=False)

        result = await self.registry.update_agent_status(
            "status-agent", AgentStatus.SUSPENDED, reason="Maintenance"
        )

        assert result is not None
        assert result.status == AgentStatus.SUSPENDED

    @pytest.mark.asyncio
    async def test_update_agent_status_not_found(self):
        """Test updating status of nonexistent agent."""
        result = await self.registry.update_agent_status(
            "nonexistent", AgentStatus.SUSPENDED
        )
        assert result is None


class TestA2AAgentRegistryDiscovery:
    """Tests for agent discovery and search."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = A2AAgentRegistry()

    @pytest.mark.asyncio
    async def test_get_agent(self):
        """Test getting an agent by ID."""
        card = MockAgentCard(agent_id="get-agent")
        await self.registry.register_agent(card, verify=False)

        result = await self.registry.get_agent("get-agent")
        assert result is not None
        assert result.agent_id == "get-agent"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self):
        """Test getting a nonexistent agent."""
        result = await self.registry.get_agent("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_agents(self):
        """Test listing all agents."""
        for i in range(5):
            card = MockAgentCard(agent_id=f"agent-{i}")
            await self.registry.register_agent(card, verify=False)

        result = await self.registry.list_agents()
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_list_agents_with_status_filter(self):
        """Test listing agents with status filter."""
        card1 = MockAgentCard(agent_id="active-1")
        card2 = MockAgentCard(agent_id="active-2")
        card3 = MockAgentCard(agent_id="suspended")

        await self.registry.register_agent(card1, verify=False)
        await self.registry.register_agent(card2, verify=False)
        await self.registry.register_agent(card3, verify=False)
        await self.registry.update_agent_status("suspended", AgentStatus.SUSPENDED)

        active = await self.registry.list_agents(status=AgentStatus.ACTIVE)
        assert len(active) == 2

        suspended = await self.registry.list_agents(status=AgentStatus.SUSPENDED)
        assert len(suspended) == 1

    @pytest.mark.asyncio
    async def test_list_agents_pagination(self):
        """Test listing agents with pagination."""
        for i in range(10):
            card = MockAgentCard(agent_id=f"agent-{i}")
            await self.registry.register_agent(card, verify=False)

        page1 = await self.registry.list_agents(limit=5, offset=0)
        page2 = await self.registry.list_agents(limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5

    @pytest.mark.asyncio
    async def test_search_agents_by_capability(self):
        """Test searching agents by capability."""
        caps1 = [MockAgentCapability("code_review")]
        caps2 = [MockAgentCapability("testing")]
        caps3 = [MockAgentCapability("code_review"), MockAgentCapability("testing")]

        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-1", capabilities=caps1), verify=False
        )
        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-2", capabilities=caps2), verify=False
        )
        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-3", capabilities=caps3), verify=False
        )

        criteria = AgentSearchCriteria(capability_name="code_review")
        results = await self.registry.search_agents(criteria)

        assert len(results) == 2
        agent_ids = {a.agent_id for a in results}
        assert "agent-1" in agent_ids
        assert "agent-3" in agent_ids

    @pytest.mark.asyncio
    async def test_search_agents_by_status(self):
        """Test searching agents by status."""
        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-1"), verify=False
        )
        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-2"), verify=False
        )
        await self.registry.update_agent_status("agent-2", AgentStatus.DEGRADED)

        criteria = AgentSearchCriteria(status=AgentStatus.ACTIVE)
        results = await self.registry.search_agents(criteria)

        assert len(results) == 1
        assert results[0].agent_id == "agent-1"

    @pytest.mark.asyncio
    async def test_search_agents_by_provider(self):
        """Test searching agents by provider."""
        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-1", provider="ProviderA"), verify=False
        )
        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-2", provider="ProviderB"), verify=False
        )

        criteria = AgentSearchCriteria(provider="ProviderA")
        results = await self.registry.search_agents(criteria)

        assert len(results) == 1
        assert results[0].agent_id == "agent-1"

    @pytest.mark.asyncio
    async def test_search_agents_by_trust_level(self):
        """Test searching agents by trust level."""
        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-1", provider="aenealabs"), verify=False
        )
        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-2", provider="unknown"), verify=False
        )

        criteria = AgentSearchCriteria(trust_level=AgentTrustLevel.VERIFIED)
        results = await self.registry.search_agents(criteria)

        assert len(results) == 1
        assert results[0].agent_id == "agent-1"

    @pytest.mark.asyncio
    async def test_search_agents_by_success_rate(self):
        """Test searching agents by minimum success rate."""
        # Register and set up task history
        await self.registry.register_agent(
            MockAgentCard(agent_id="high-success"), verify=False
        )
        await self.registry.register_agent(
            MockAgentCard(agent_id="low-success"), verify=False
        )

        # Record completions
        high = self.registry._agents["high-success"]
        high.total_tasks_completed = 95
        high.total_tasks_failed = 5

        low = self.registry._agents["low-success"]
        low.total_tasks_completed = 50
        low.total_tasks_failed = 50

        criteria = AgentSearchCriteria(min_success_rate=0.9)
        results = await self.registry.search_agents(criteria)

        assert len(results) == 1
        assert results[0].agent_id == "high-success"

    @pytest.mark.asyncio
    async def test_search_agents_by_max_latency(self):
        """Test searching agents by maximum latency."""
        await self.registry.register_agent(
            MockAgentCard(agent_id="fast-agent"), verify=False
        )
        await self.registry.register_agent(
            MockAgentCard(agent_id="slow-agent"), verify=False
        )

        self.registry._agents["fast-agent"].average_latency_ms = 100.0
        self.registry._agents["slow-agent"].average_latency_ms = 5000.0

        criteria = AgentSearchCriteria(max_latency_ms=1000.0)
        results = await self.registry.search_agents(criteria)

        assert len(results) == 1
        assert results[0].agent_id == "fast-agent"

    @pytest.mark.asyncio
    async def test_search_agents_by_tags(self):
        """Test searching agents by tags."""
        await self.registry.register_agent(
            MockAgentCard(agent_id="tagged-agent"),
            tags=["production", "critical"],
            verify=False,
        )
        await self.registry.register_agent(
            MockAgentCard(agent_id="untagged-agent"),
            tags=[],
            verify=False,
        )

        criteria = AgentSearchCriteria(tags=["production"])
        results = await self.registry.search_agents(criteria)

        assert len(results) == 1
        assert results[0].agent_id == "tagged-agent"

    @pytest.mark.asyncio
    async def test_find_agents_for_capability(self):
        """Test finding healthy agents for a capability."""
        caps = [MockAgentCapability("generate_patch")]
        await self.registry.register_agent(
            MockAgentCard(agent_id="patcher", capabilities=caps), verify=False
        )

        results = await self.registry.find_agents_for_capability(
            "generate_patch", min_success_rate=0.5
        )

        assert len(results) == 1
        assert results[0].agent_id == "patcher"


class TestA2AAgentRegistryHealthMonitoring:
    """Tests for health monitoring."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = A2AAgentRegistry(health_check_interval=0.1)

    @pytest.mark.asyncio
    async def test_start_health_monitoring(self):
        """Test starting health monitoring."""
        await self.registry.start_health_monitoring()
        assert self.registry._health_check_task is not None
        await self.registry.stop_health_monitoring()

    @pytest.mark.asyncio
    async def test_stop_health_monitoring(self):
        """Test stopping health monitoring."""
        await self.registry.start_health_monitoring()
        await self.registry.stop_health_monitoring()
        assert self.registry._health_check_task is None

    @pytest.mark.asyncio
    async def test_health_check_recovers_agent(self):
        """Test that passing health check recovers degraded agent."""
        card = MockAgentCard(agent_id="test-agent")
        await self.registry.register_agent(card, verify=False)

        agent = self.registry._agents["test-agent"]
        agent.status = AgentStatus.DEGRADED
        agent.health_check_failures = 1

        await self.registry._perform_health_checks()

        assert agent.status == AgentStatus.ACTIVE
        assert agent.health_check_failures == 0

    @pytest.mark.asyncio
    async def test_health_check_marks_inactive_after_failures(self):
        """Test that agent is marked inactive after 3 failures."""
        card = MockAgentCard(agent_id="failing-agent")
        await self.registry.register_agent(card, verify=False)

        agent = self.registry._agents["failing-agent"]
        agent.health_check_failures = 2

        # Mock failing health check
        with patch.object(
            self.registry, "_check_agent_health", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = False
            await self.registry._perform_health_checks()

        assert agent.status == AgentStatus.INACTIVE
        assert agent.health_check_failures == 3

    @pytest.mark.asyncio
    async def test_health_check_skips_suspended(self):
        """Test that suspended agents are skipped in health checks."""
        card = MockAgentCard(agent_id="suspended-agent")
        await self.registry.register_agent(card, verify=False)
        await self.registry.update_agent_status(
            "suspended-agent", AgentStatus.SUSPENDED
        )

        initial_failures = self.registry._agents[
            "suspended-agent"
        ].health_check_failures

        await self.registry._perform_health_checks()

        # Should not have changed
        assert (
            self.registry._agents["suspended-agent"].health_check_failures
            == initial_failures
        )

    @pytest.mark.asyncio
    async def test_verify_agent_success(self):
        """Test successful agent verification."""
        card = MockAgentCard(agent_id="verify-agent")
        agent = RegisteredAgent(
            agent_card=card,
            status=AgentStatus.PENDING,
        )

        await self.registry._verify_agent(agent)
        assert agent.status == AgentStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_verify_agent_failure(self):
        """Test failed agent verification."""
        card = MockAgentCard(agent_id="fail-verify")
        agent = RegisteredAgent(
            agent_card=card,
            status=AgentStatus.PENDING,
        )

        with patch.object(
            self.registry, "_check_agent_health", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = False
            await self.registry._verify_agent(agent)

        assert agent.status == AgentStatus.INACTIVE


class TestA2AAgentRegistryMetrics:
    """Tests for registry metrics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = A2AAgentRegistry()

    @pytest.mark.asyncio
    async def test_get_metrics_empty(self):
        """Test metrics with empty registry."""
        metrics = self.registry.get_metrics()

        assert metrics["total_registered_agents"] == 0
        assert metrics["total_registrations"] == 0
        assert metrics["total_searches"] == 0

    @pytest.mark.asyncio
    async def test_get_metrics_with_agents(self):
        """Test metrics with registered agents."""
        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-1"), verify=False
        )
        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-2", provider="anthropic"), verify=False
        )

        metrics = self.registry.get_metrics()

        assert metrics["total_registered_agents"] == 2
        assert metrics["total_registrations"] == 2
        assert "agents_by_status" in metrics
        assert "agents_by_trust" in metrics

    @pytest.mark.asyncio
    async def test_metrics_track_searches(self):
        """Test that metrics track search count."""
        await self.registry.register_agent(
            MockAgentCard(agent_id="agent-1"), verify=False
        )

        await self.registry.search_agents(AgentSearchCriteria())
        await self.registry.search_agents(AgentSearchCriteria())

        metrics = self.registry.get_metrics()
        assert metrics["total_searches"] == 2


class TestA2AAgentRegistryBulkOperations:
    """Tests for bulk operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = A2AAgentRegistry()

    @pytest.mark.asyncio
    async def test_import_agents_from_discovery(self):
        """Test importing agents from discovery endpoint."""
        result = await self.registry.import_agents_from_discovery(
            "https://discovery.example.com"
        )
        # Mock returns empty list
        assert result == []

    @pytest.mark.asyncio
    async def test_export_registry(self):
        """Test exporting the registry."""
        await self.registry.register_agent(
            MockAgentCard(agent_id="export-agent"), verify=False
        )

        result = await self.registry.export_registry()

        assert "agents" in result
        assert len(result["agents"]) == 1
        assert "metrics" in result
        assert "exported_at" in result


# =============================================================================
# Exception Tests
# =============================================================================


class TestRegistryExceptions:
    """Tests for registry exceptions."""

    def test_registry_error(self):
        """Test base RegistryError."""
        error = RegistryError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_agent_not_found_error(self):
        """Test AgentNotFoundError."""
        error = AgentNotFoundError("Agent not found")
        assert str(error) == "Agent not found"
        assert isinstance(error, RegistryError)

    def test_agent_already_exists_error(self):
        """Test AgentAlreadyExistsError."""
        error = AgentAlreadyExistsError("Agent exists")
        assert str(error) == "Agent exists"
        assert isinstance(error, RegistryError)

    def test_registration_error(self):
        """Test RegistrationError."""
        error = RegistrationError("Registration failed")
        assert str(error) == "Registration failed"
        assert isinstance(error, RegistryError)
