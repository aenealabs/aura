"""
Project Aura - Agent Discovery Engine

Continuous inventory of all agents, MCP servers, tool registrations,
and LLM endpoints. Integrates with ADR-066 Capability Governance
registry as source of truth for registered agents.

Based on ADR-083: Runtime Agent Security Platform

Compliance:
- NIST 800-53 CM-8: Information system component inventory
- NIST 800-53 SI-4: Information system monitoring
- NIST 800-53 PM-5: System inventory
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Status of a discovered agent."""

    ACTIVE = "active"
    IDLE = "idle"
    UNRESPONSIVE = "unresponsive"
    DEREGISTERED = "deregistered"
    SHADOW = "shadow"


@dataclass(frozen=True)
class AgentRegistration:
    """Immutable record of a discovered agent."""

    agent_id: str
    agent_type: str
    registered: bool
    first_seen: datetime
    last_seen: datetime
    tool_capabilities: tuple[str, ...]
    mcp_servers: tuple[str, ...]
    llm_endpoints: tuple[str, ...]
    is_shadow: bool
    status: AgentStatus
    event_count: int = 0
    metadata: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "registered": self.registered,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "tool_capabilities": list(self.tool_capabilities),
            "mcp_servers": list(self.mcp_servers),
            "llm_endpoints": list(self.llm_endpoints),
            "is_shadow": self.is_shadow,
            "status": self.status.value,
            "event_count": self.event_count,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MCPServerRegistration:
    """Immutable record of a discovered MCP server."""

    server_id: str
    server_name: str
    endpoint: str
    registered: bool
    tools_provided: tuple[str, ...]
    first_seen: datetime
    last_seen: datetime
    is_shadow: bool

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "server_id": self.server_id,
            "server_name": self.server_name,
            "endpoint": self.endpoint,
            "registered": self.registered,
            "tools_provided": list(self.tools_provided),
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "is_shadow": self.is_shadow,
        }


class AgentDiscoveryService:
    """
    Continuous agent inventory and discovery engine.

    Tracks all agents observed in traffic and cross-references with
    the ADR-066 Capability Governance registry to detect unregistered
    (shadow) agents.

    Usage:
        discovery = AgentDiscoveryService(
            registered_agents={"coder-agent", "reviewer-agent"},
        )

        # Record agent activity from intercepted traffic
        discovery.record_agent_activity(
            agent_id="coder-agent",
            agent_type="coder",
            tools_used=["semantic_search"],
        )

        # Check for shadow agents
        shadows = discovery.get_shadow_agents()
    """

    def __init__(
        self,
        registered_agents: Optional[set[str]] = None,
        registered_mcp_servers: Optional[set[str]] = None,
        idle_timeout: timedelta = timedelta(minutes=30),
        unresponsive_timeout: timedelta = timedelta(hours=2),
    ):
        self.registered_agents = registered_agents or set()
        self.registered_mcp_servers = registered_mcp_servers or set()
        self.idle_timeout = idle_timeout
        self.unresponsive_timeout = unresponsive_timeout

        # Internal tracking
        self._agents: dict[str, _MutableAgentRecord] = {}
        self._mcp_servers: dict[str, _MutableMCPRecord] = {}
        self._activity_log: list[dict[str, Any]] = []

    def record_agent_activity(
        self,
        agent_id: str,
        agent_type: str = "unknown",
        tools_used: Optional[list[str]] = None,
        mcp_servers_used: Optional[list[str]] = None,
        llm_endpoints_used: Optional[list[str]] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> AgentRegistration:
        """
        Record agent activity from intercepted traffic.

        Args:
            agent_id: Unique identifier of the agent.
            agent_type: Type of agent (coder, reviewer, validator, etc.).
            tools_used: Tools invoked by this agent.
            mcp_servers_used: MCP servers accessed.
            llm_endpoints_used: LLM endpoints called.
            metadata: Additional metadata.

        Returns:
            Current registration state of the agent.
        """
        now = datetime.now(timezone.utc)

        if agent_id not in self._agents:
            self._agents[agent_id] = _MutableAgentRecord(
                agent_id=agent_id,
                agent_type=agent_type,
                first_seen=now,
            )

        record = self._agents[agent_id]
        record.last_seen = now
        record.event_count += 1

        if tools_used:
            record.tools.update(tools_used)
        if mcp_servers_used:
            record.mcp_servers.update(mcp_servers_used)
        if llm_endpoints_used:
            record.llm_endpoints.update(llm_endpoints_used)
        if metadata:
            record.metadata.update(metadata)

        # Log activity
        self._activity_log.append(
            {
                "agent_id": agent_id,
                "timestamp": now.isoformat(),
                "tools": tools_used or [],
                "mcp_servers": mcp_servers_used or [],
            }
        )

        return self._to_registration(record)

    def record_mcp_server(
        self,
        server_id: str,
        server_name: str,
        endpoint: str,
        tools_provided: Optional[list[str]] = None,
    ) -> MCPServerRegistration:
        """Record an observed MCP server."""
        now = datetime.now(timezone.utc)

        if server_id not in self._mcp_servers:
            self._mcp_servers[server_id] = _MutableMCPRecord(
                server_id=server_id,
                server_name=server_name,
                endpoint=endpoint,
                first_seen=now,
            )

        record = self._mcp_servers[server_id]
        record.last_seen = now
        if tools_provided:
            record.tools.update(tools_provided)

        return self._to_mcp_registration(record)

    def get_agent(self, agent_id: str) -> Optional[AgentRegistration]:
        """Get registration for a specific agent."""
        record = self._agents.get(agent_id)
        if record is None:
            return None
        return self._to_registration(record)

    def get_all_agents(self) -> list[AgentRegistration]:
        """Get all discovered agents."""
        return [self._to_registration(r) for r in self._agents.values()]

    def get_active_agents(self) -> list[AgentRegistration]:
        """Get agents with ACTIVE status."""
        return [
            reg for reg in self.get_all_agents() if reg.status == AgentStatus.ACTIVE
        ]

    def get_shadow_agents(self) -> list[AgentRegistration]:
        """Get agents not in the capability registry."""
        return [reg for reg in self.get_all_agents() if reg.is_shadow]

    def get_all_mcp_servers(self) -> list[MCPServerRegistration]:
        """Get all discovered MCP servers."""
        return [self._to_mcp_registration(r) for r in self._mcp_servers.values()]

    def get_shadow_mcp_servers(self) -> list[MCPServerRegistration]:
        """Get MCP servers not in the registered set."""
        return [reg for reg in self.get_all_mcp_servers() if reg.is_shadow]

    def update_registry(
        self,
        registered_agents: Optional[set[str]] = None,
        registered_mcp_servers: Optional[set[str]] = None,
    ) -> None:
        """Update the set of registered agents/servers (from ADR-066 registry refresh)."""
        if registered_agents is not None:
            self.registered_agents = registered_agents
        if registered_mcp_servers is not None:
            self.registered_mcp_servers = registered_mcp_servers

    @property
    def total_agents(self) -> int:
        """Total number of discovered agents."""
        return len(self._agents)

    @property
    def total_shadow_agents(self) -> int:
        """Number of shadow (unregistered) agents."""
        return sum(
            1 for r in self._agents.values() if r.agent_id not in self.registered_agents
        )

    @property
    def total_mcp_servers(self) -> int:
        """Total number of discovered MCP servers."""
        return len(self._mcp_servers)

    @property
    def activity_count(self) -> int:
        """Total recorded activity events."""
        return len(self._activity_log)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _determine_status(self, record: "_MutableAgentRecord") -> AgentStatus:
        """Determine agent status based on activity recency."""
        now = datetime.now(timezone.utc)
        time_since_seen = now - record.last_seen

        if record.agent_id not in self.registered_agents:
            return AgentStatus.SHADOW
        if time_since_seen > self.unresponsive_timeout:
            return AgentStatus.UNRESPONSIVE
        if time_since_seen > self.idle_timeout:
            return AgentStatus.IDLE
        return AgentStatus.ACTIVE

    def _to_registration(self, record: "_MutableAgentRecord") -> AgentRegistration:
        """Convert mutable record to frozen registration."""
        is_shadow = record.agent_id not in self.registered_agents
        return AgentRegistration(
            agent_id=record.agent_id,
            agent_type=record.agent_type,
            registered=not is_shadow,
            first_seen=record.first_seen,
            last_seen=record.last_seen,
            tool_capabilities=tuple(sorted(record.tools)),
            mcp_servers=tuple(sorted(record.mcp_servers)),
            llm_endpoints=tuple(sorted(record.llm_endpoints)),
            is_shadow=is_shadow,
            status=self._determine_status(record),
            event_count=record.event_count,
            metadata=tuple(sorted(record.metadata.items())),
        )

    def _to_mcp_registration(
        self, record: "_MutableMCPRecord"
    ) -> MCPServerRegistration:
        """Convert mutable MCP record to frozen registration."""
        is_shadow = record.server_id not in self.registered_mcp_servers
        return MCPServerRegistration(
            server_id=record.server_id,
            server_name=record.server_name,
            endpoint=record.endpoint,
            registered=not is_shadow,
            tools_provided=tuple(sorted(record.tools)),
            first_seen=record.first_seen,
            last_seen=record.last_seen,
            is_shadow=is_shadow,
        )


class _MutableAgentRecord:
    """Internal mutable tracking record for an agent."""

    def __init__(self, agent_id: str, agent_type: str, first_seen: datetime):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.first_seen = first_seen
        self.last_seen = first_seen
        self.tools: set[str] = set()
        self.mcp_servers: set[str] = set()
        self.llm_endpoints: set[str] = set()
        self.event_count: int = 0
        self.metadata: dict[str, str] = {}


class _MutableMCPRecord:
    """Internal mutable tracking record for an MCP server."""

    def __init__(
        self, server_id: str, server_name: str, endpoint: str, first_seen: datetime
    ):
        self.server_id = server_id
        self.server_name = server_name
        self.endpoint = endpoint
        self.first_seen = first_seen
        self.last_seen = first_seen
        self.tools: set[str] = set()


# Singleton instance
_discovery_instance: Optional[AgentDiscoveryService] = None


def get_agent_discovery() -> AgentDiscoveryService:
    """Get singleton agent discovery instance."""
    global _discovery_instance
    if _discovery_instance is None:
        _discovery_instance = AgentDiscoveryService()
    return _discovery_instance


def reset_agent_discovery() -> None:
    """Reset agent discovery singleton (for testing)."""
    global _discovery_instance
    _discovery_instance = None
