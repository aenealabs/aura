"""
Tests for the Agent Discovery Service.

Covers AgentDiscoveryService operations, AgentRegistration / MCPServerRegistration
frozen dataclasses, AgentStatus determination, singleton lifecycle, and
registry update semantics.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.runtime_security.discovery import (
    AgentDiscoveryService,
    get_agent_discovery,
    reset_agent_discovery,
)
from src.services.runtime_security.discovery.agent_discovery import (
    AgentRegistration,
    AgentStatus,
    MCPServerRegistration,
)

# ---------------------------------------------------------------------------
# AgentRegistration frozen dataclass
# ---------------------------------------------------------------------------


class TestAgentRegistration:
    """Tests for the AgentRegistration frozen dataclass."""

    def test_create_registration(self):
        """Test creating an AgentRegistration with all fields."""
        now = datetime.now(timezone.utc)
        reg = AgentRegistration(
            agent_id="test-agent",
            agent_type="coder",
            registered=True,
            first_seen=now,
            last_seen=now,
            tool_capabilities=("read_logs", "semantic_search"),
            mcp_servers=("mcp-tools",),
            llm_endpoints=("bedrock-claude",),
            is_shadow=False,
            status=AgentStatus.ACTIVE,
            event_count=5,
            metadata=(("team", "platform"),),
        )
        assert reg.agent_id == "test-agent"
        assert reg.agent_type == "coder"
        assert reg.registered is True
        assert reg.is_shadow is False
        assert reg.status == AgentStatus.ACTIVE
        assert reg.event_count == 5

    def test_registration_is_frozen(self):
        """Test that AgentRegistration fields cannot be mutated."""
        now = datetime.now(timezone.utc)
        reg = AgentRegistration(
            agent_id="immutable-agent",
            agent_type="validator",
            registered=True,
            first_seen=now,
            last_seen=now,
            tool_capabilities=(),
            mcp_servers=(),
            llm_endpoints=(),
            is_shadow=False,
            status=AgentStatus.IDLE,
        )
        with pytest.raises(AttributeError):
            reg.agent_id = "new-id"  # type: ignore[misc]

    def test_to_dict_serialization(self):
        """Test to_dict produces expected keys and value types."""
        now = datetime.now(timezone.utc)
        reg = AgentRegistration(
            agent_id="dict-agent",
            agent_type="reviewer",
            registered=False,
            first_seen=now,
            last_seen=now,
            tool_capabilities=("write_file",),
            mcp_servers=("mcp-search",),
            llm_endpoints=("bedrock-claude",),
            is_shadow=True,
            status=AgentStatus.SHADOW,
            event_count=3,
            metadata=(("env", "dev"),),
        )
        d = reg.to_dict()

        assert d["agent_id"] == "dict-agent"
        assert d["agent_type"] == "reviewer"
        assert d["registered"] is False
        assert d["is_shadow"] is True
        assert d["status"] == "shadow"
        assert d["event_count"] == 3
        assert d["tool_capabilities"] == ["write_file"]
        assert d["mcp_servers"] == ["mcp-search"]
        assert d["llm_endpoints"] == ["bedrock-claude"]
        assert d["metadata"] == {"env": "dev"}
        assert d["first_seen"] == now.isoformat()
        assert d["last_seen"] == now.isoformat()

    def test_to_dict_empty_metadata(self):
        """Test to_dict with default empty metadata tuple."""
        now = datetime.now(timezone.utc)
        reg = AgentRegistration(
            agent_id="empty-meta",
            agent_type="coder",
            registered=True,
            first_seen=now,
            last_seen=now,
            tool_capabilities=(),
            mcp_servers=(),
            llm_endpoints=(),
            is_shadow=False,
            status=AgentStatus.ACTIVE,
        )
        d = reg.to_dict()
        assert d["metadata"] == {}
        assert d["event_count"] == 0


# ---------------------------------------------------------------------------
# MCPServerRegistration frozen dataclass
# ---------------------------------------------------------------------------


class TestMCPServerRegistration:
    """Tests for the MCPServerRegistration frozen dataclass."""

    def test_create_mcp_registration(self):
        """Test creating an MCPServerRegistration."""
        now = datetime.now(timezone.utc)
        reg = MCPServerRegistration(
            server_id="mcp-1",
            server_name="Tools Server",
            endpoint="http://mcp-tools:8080",
            registered=True,
            tools_provided=("search", "index"),
            first_seen=now,
            last_seen=now,
            is_shadow=False,
        )
        assert reg.server_id == "mcp-1"
        assert reg.server_name == "Tools Server"
        assert reg.endpoint == "http://mcp-tools:8080"
        assert reg.registered is True
        assert reg.is_shadow is False
        assert reg.tools_provided == ("search", "index")

    def test_mcp_registration_is_frozen(self):
        """Test that MCPServerRegistration is immutable."""
        now = datetime.now(timezone.utc)
        reg = MCPServerRegistration(
            server_id="mcp-frozen",
            server_name="Frozen",
            endpoint="http://localhost",
            registered=True,
            tools_provided=(),
            first_seen=now,
            last_seen=now,
            is_shadow=False,
        )
        with pytest.raises(AttributeError):
            reg.server_id = "new-id"  # type: ignore[misc]

    def test_mcp_to_dict_serialization(self):
        """Test MCPServerRegistration.to_dict serialization."""
        now = datetime.now(timezone.utc)
        reg = MCPServerRegistration(
            server_id="mcp-dict",
            server_name="Dict Server",
            endpoint="http://dict:8080",
            registered=False,
            tools_provided=("tool_a", "tool_b"),
            first_seen=now,
            last_seen=now,
            is_shadow=True,
        )
        d = reg.to_dict()

        assert d["server_id"] == "mcp-dict"
        assert d["server_name"] == "Dict Server"
        assert d["endpoint"] == "http://dict:8080"
        assert d["registered"] is False
        assert d["is_shadow"] is True
        assert d["tools_provided"] == ["tool_a", "tool_b"]
        assert d["first_seen"] == now.isoformat()
        assert d["last_seen"] == now.isoformat()


# ---------------------------------------------------------------------------
# AgentStatus enum
# ---------------------------------------------------------------------------


class TestAgentStatus:
    """Tests for AgentStatus enum values."""

    def test_all_status_values_exist(self):
        """Test that all expected status values exist."""
        assert AgentStatus.ACTIVE.value == "active"
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.UNRESPONSIVE.value == "unresponsive"
        assert AgentStatus.DEREGISTERED.value == "deregistered"
        assert AgentStatus.SHADOW.value == "shadow"

    def test_status_count(self):
        """Test that there are exactly 5 statuses."""
        assert len(AgentStatus) == 5


# ---------------------------------------------------------------------------
# AgentDiscoveryService - record_agent_activity
# ---------------------------------------------------------------------------


class TestRecordAgentActivity:
    """Tests for recording agent activity."""

    def test_record_new_agent(self, discovery_service):
        """Test recording activity from a brand-new agent."""
        reg = discovery_service.record_agent_activity(
            agent_id="coder-agent",
            agent_type="coder",
        )
        assert reg.agent_id == "coder-agent"
        assert reg.agent_type == "coder"
        assert reg.registered is True
        assert reg.is_shadow is False
        assert reg.event_count == 1

    def test_record_shadow_agent(self, discovery_service):
        """Test recording activity from an unregistered agent."""
        reg = discovery_service.record_agent_activity(
            agent_id="unknown-agent",
            agent_type="rogue",
        )
        assert reg.agent_id == "unknown-agent"
        assert reg.registered is False
        assert reg.is_shadow is True
        assert reg.status == AgentStatus.SHADOW

    def test_record_with_tools(self, discovery_service):
        """Test recording activity with tools."""
        reg = discovery_service.record_agent_activity(
            agent_id="coder-agent",
            agent_type="coder",
            tools_used=["semantic_search", "code_search"],
        )
        assert "semantic_search" in reg.tool_capabilities
        assert "code_search" in reg.tool_capabilities

    def test_record_with_mcp_servers(self, discovery_service):
        """Test recording activity with MCP servers."""
        reg = discovery_service.record_agent_activity(
            agent_id="coder-agent",
            agent_type="coder",
            mcp_servers_used=["mcp-tools-server"],
        )
        assert "mcp-tools-server" in reg.mcp_servers

    def test_record_with_llm_endpoints(self, discovery_service):
        """Test recording activity with LLM endpoints."""
        reg = discovery_service.record_agent_activity(
            agent_id="coder-agent",
            agent_type="coder",
            llm_endpoints_used=["bedrock-claude", "bedrock-titan"],
        )
        assert "bedrock-claude" in reg.llm_endpoints
        assert "bedrock-titan" in reg.llm_endpoints

    def test_record_with_metadata(self, discovery_service):
        """Test recording activity with metadata."""
        reg = discovery_service.record_agent_activity(
            agent_id="coder-agent",
            agent_type="coder",
            metadata={"team": "platform", "version": "2.1"},
        )
        meta_dict = dict(reg.metadata)
        assert meta_dict["team"] == "platform"
        assert meta_dict["version"] == "2.1"

    def test_multiple_activities_increment_event_count(self, discovery_service):
        """Test that successive activities increment event_count."""
        discovery_service.record_agent_activity(
            agent_id="coder-agent", agent_type="coder"
        )
        discovery_service.record_agent_activity(
            agent_id="coder-agent", agent_type="coder"
        )
        reg = discovery_service.record_agent_activity(
            agent_id="coder-agent", agent_type="coder"
        )
        assert reg.event_count == 3

    def test_tools_accumulate_across_activities(self, discovery_service):
        """Test that tools from multiple activities are accumulated."""
        discovery_service.record_agent_activity(
            agent_id="coder-agent",
            agent_type="coder",
            tools_used=["tool_a"],
        )
        reg = discovery_service.record_agent_activity(
            agent_id="coder-agent",
            agent_type="coder",
            tools_used=["tool_b"],
        )
        assert set(reg.tool_capabilities) == {"tool_a", "tool_b"}

    def test_activity_log_grows(self, discovery_service):
        """Test that internal activity log is maintained."""
        discovery_service.record_agent_activity(
            agent_id="coder-agent", agent_type="coder"
        )
        discovery_service.record_agent_activity(
            agent_id="reviewer-agent", agent_type="reviewer"
        )
        assert discovery_service.activity_count == 2


# ---------------------------------------------------------------------------
# AgentDiscoveryService - record_mcp_server
# ---------------------------------------------------------------------------


class TestRecordMCPServer:
    """Tests for recording MCP server observations."""

    def test_record_registered_mcp_server(self, discovery_service):
        """Test recording a registered MCP server."""
        reg = discovery_service.record_mcp_server(
            server_id="mcp-tools-server",
            server_name="Tools Server",
            endpoint="http://mcp-tools:8080",
        )
        assert reg.server_id == "mcp-tools-server"
        assert reg.registered is True
        assert reg.is_shadow is False

    def test_record_shadow_mcp_server(self, discovery_service):
        """Test recording an unregistered MCP server."""
        reg = discovery_service.record_mcp_server(
            server_id="unknown-mcp",
            server_name="Unknown",
            endpoint="http://unknown:9999",
        )
        assert reg.server_id == "unknown-mcp"
        assert reg.registered is False
        assert reg.is_shadow is True

    def test_record_mcp_server_with_tools(self, discovery_service):
        """Test recording an MCP server with tools."""
        reg = discovery_service.record_mcp_server(
            server_id="mcp-tools-server",
            server_name="Tools Server",
            endpoint="http://mcp-tools:8080",
            tools_provided=["search", "index", "embed"],
        )
        assert set(reg.tools_provided) == {"search", "index", "embed"}

    def test_mcp_tools_accumulate(self, discovery_service):
        """Test that MCP tools accumulate across observations."""
        discovery_service.record_mcp_server(
            server_id="mcp-tools-server",
            server_name="Tools Server",
            endpoint="http://mcp-tools:8080",
            tools_provided=["search"],
        )
        reg = discovery_service.record_mcp_server(
            server_id="mcp-tools-server",
            server_name="Tools Server",
            endpoint="http://mcp-tools:8080",
            tools_provided=["index"],
        )
        assert set(reg.tools_provided) == {"search", "index"}


# ---------------------------------------------------------------------------
# AgentDiscoveryService - retrieval methods
# ---------------------------------------------------------------------------


class TestAgentRetrieval:
    """Tests for agent retrieval methods."""

    def test_get_agent_exists(self, populated_discovery):
        """Test retrieving a known agent."""
        reg = populated_discovery.get_agent("coder-agent")
        assert reg is not None
        assert reg.agent_id == "coder-agent"

    def test_get_agent_not_found(self, discovery_service):
        """Test retrieving a nonexistent agent returns None."""
        assert discovery_service.get_agent("nonexistent") is None

    def test_get_all_agents(self, populated_discovery):
        """Test get_all_agents returns all discovered agents."""
        agents = populated_discovery.get_all_agents()
        ids = {a.agent_id for a in agents}
        assert "coder-agent" in ids
        assert "reviewer-agent" in ids
        assert "rogue-agent" in ids

    def test_get_active_agents(self, populated_discovery):
        """Test get_active_agents returns only ACTIVE agents."""
        active = populated_discovery.get_active_agents()
        for a in active:
            assert a.status == AgentStatus.ACTIVE
        # Registered agents with recent activity should be active
        active_ids = {a.agent_id for a in active}
        assert "coder-agent" in active_ids
        assert "reviewer-agent" in active_ids
        # Shadow agent should not be ACTIVE (it should be SHADOW)
        assert "rogue-agent" not in active_ids

    def test_get_shadow_agents(self, populated_discovery):
        """Test get_shadow_agents returns only unregistered agents."""
        shadows = populated_discovery.get_shadow_agents()
        shadow_ids = {a.agent_id for a in shadows}
        assert "rogue-agent" in shadow_ids
        assert "coder-agent" not in shadow_ids

    def test_get_all_mcp_servers(self, populated_discovery):
        """Test retrieving all MCP servers."""
        servers = populated_discovery.get_all_mcp_servers()
        ids = {s.server_id for s in servers}
        assert "mcp-tools-server" in ids
        assert "shadow-mcp" in ids

    def test_get_shadow_mcp_servers(self, populated_discovery):
        """Test retrieving only shadow MCP servers."""
        shadows = populated_discovery.get_shadow_mcp_servers()
        shadow_ids = {s.server_id for s in shadows}
        assert "shadow-mcp" in shadow_ids
        assert "mcp-tools-server" not in shadow_ids


# ---------------------------------------------------------------------------
# AgentDiscoveryService - status determination
# ---------------------------------------------------------------------------


class TestAgentStatusDetermination:
    """Tests for AgentStatus determination based on recency."""

    def test_recently_active_agent_is_active(self, discovery_service):
        """Test that a recently-seen registered agent is ACTIVE."""
        reg = discovery_service.record_agent_activity(
            agent_id="coder-agent", agent_type="coder"
        )
        assert reg.status == AgentStatus.ACTIVE

    def test_unregistered_agent_is_shadow(self, discovery_service):
        """Test that an unregistered agent is SHADOW regardless of recency."""
        reg = discovery_service.record_agent_activity(
            agent_id="shadow-agent", agent_type="unknown"
        )
        assert reg.status == AgentStatus.SHADOW

    def test_idle_agent_status(self):
        """Test that an agent idle beyond the timeout gets IDLE status."""
        service = AgentDiscoveryService(
            registered_agents={"test-agent"},
            idle_timeout=timedelta(seconds=0),
            unresponsive_timeout=timedelta(hours=2),
        )
        reg = service.record_agent_activity(agent_id="test-agent", agent_type="coder")
        # With idle_timeout=0, the agent should be IDLE immediately after
        # since any positive time_since_seen > 0.
        # We retrieve again to trigger a fresh _determine_status call.
        retrieved = service.get_agent("test-agent")
        assert retrieved is not None
        # Due to tiny time elapsed vs zero timeout, should be IDLE or UNRESPONSIVE
        assert retrieved.status in (AgentStatus.IDLE, AgentStatus.UNRESPONSIVE)

    def test_unresponsive_agent_status(self):
        """Test that an agent past unresponsive timeout gets UNRESPONSIVE."""
        service = AgentDiscoveryService(
            registered_agents={"test-agent"},
            idle_timeout=timedelta(seconds=0),
            unresponsive_timeout=timedelta(seconds=0),
        )
        service.record_agent_activity(agent_id="test-agent", agent_type="coder")
        retrieved = service.get_agent("test-agent")
        assert retrieved is not None
        assert retrieved.status == AgentStatus.UNRESPONSIVE


# ---------------------------------------------------------------------------
# AgentDiscoveryService - update_registry
# ---------------------------------------------------------------------------


class TestUpdateRegistry:
    """Tests for dynamic registry updates."""

    def test_update_registered_agents(self, discovery_service):
        """Test updating the registered agents set."""
        discovery_service.record_agent_activity(agent_id="newcomer", agent_type="coder")
        reg_before = discovery_service.get_agent("newcomer")
        assert reg_before is not None
        assert reg_before.is_shadow is True

        discovery_service.update_registry(
            registered_agents={
                "coder-agent",
                "reviewer-agent",
                "validator-agent",
                "newcomer",
            }
        )
        reg_after = discovery_service.get_agent("newcomer")
        assert reg_after is not None
        assert reg_after.is_shadow is False
        assert reg_after.registered is True

    def test_update_registered_mcp_servers(self, discovery_service):
        """Test updating the registered MCP servers set."""
        discovery_service.record_mcp_server(
            server_id="new-mcp",
            server_name="New MCP",
            endpoint="http://new:8080",
        )
        reg_before = discovery_service.get_all_mcp_servers()
        shadow_before = [s for s in reg_before if s.server_id == "new-mcp"]
        assert shadow_before[0].is_shadow is True

        discovery_service.update_registry(
            registered_mcp_servers={"mcp-tools-server", "mcp-search-server", "new-mcp"}
        )
        reg_after = discovery_service.get_all_mcp_servers()
        updated = [s for s in reg_after if s.server_id == "new-mcp"]
        assert updated[0].is_shadow is False

    def test_update_registry_partial(self, discovery_service):
        """Test that updating only agents does not change MCP servers."""
        original_mcp = discovery_service.registered_mcp_servers.copy()
        discovery_service.update_registry(registered_agents={"new-set"})
        assert discovery_service.registered_mcp_servers == original_mcp

    def test_update_registry_none_values_ignored(self, discovery_service):
        """Test that None values are ignored in update_registry."""
        original_agents = discovery_service.registered_agents.copy()
        original_mcp = discovery_service.registered_mcp_servers.copy()
        discovery_service.update_registry()
        assert discovery_service.registered_agents == original_agents
        assert discovery_service.registered_mcp_servers == original_mcp


# ---------------------------------------------------------------------------
# AgentDiscoveryService - properties
# ---------------------------------------------------------------------------


class TestDiscoveryProperties:
    """Tests for discovery service property accessors."""

    def test_total_agents(self, populated_discovery):
        """Test total_agents count."""
        assert populated_discovery.total_agents == 3

    def test_total_shadow_agents(self, populated_discovery):
        """Test total_shadow_agents count."""
        assert populated_discovery.total_shadow_agents == 1

    def test_total_mcp_servers(self, populated_discovery):
        """Test total_mcp_servers count."""
        assert populated_discovery.total_mcp_servers == 2

    def test_activity_count(self, populated_discovery):
        """Test activity_count reflects all recorded events."""
        assert populated_discovery.activity_count == 3


# ---------------------------------------------------------------------------
# Singleton lifecycle
# ---------------------------------------------------------------------------


class TestSingletonLifecycle:
    """Tests for get_agent_discovery / reset_agent_discovery."""

    def test_singleton_returns_same_instance(self):
        """Test get_agent_discovery returns the same instance."""
        svc1 = get_agent_discovery()
        svc2 = get_agent_discovery()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        """Test reset followed by get returns a new instance."""
        svc1 = get_agent_discovery()
        reset_agent_discovery()
        svc2 = get_agent_discovery()
        assert svc1 is not svc2

    def test_singleton_state_is_isolated(self):
        """Test that reset clears all state."""
        svc = get_agent_discovery()
        svc.record_agent_activity(agent_id="temp", agent_type="test")
        assert svc.total_agents == 1

        reset_agent_discovery()
        svc_new = get_agent_discovery()
        assert svc_new.total_agents == 0
