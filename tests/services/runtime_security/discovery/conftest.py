"""
Test fixtures for runtime security discovery services.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.runtime_security.discovery import (
    AgentDiscoveryService,
    AgentTopologyBuilder,
    ShadowDetector,
    reset_agent_discovery,
)
from src.services.runtime_security.discovery.agent_discovery import (
    AgentRegistration,
    AgentStatus,
    MCPServerRegistration,
)
from src.services.runtime_security.discovery.shadow_detector import ShadowAlertSeverity


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all discovery singletons before and after each test."""
    reset_agent_discovery()
    yield
    reset_agent_discovery()


@pytest.fixture
def discovery_service() -> AgentDiscoveryService:
    """Create a discovery service with a known set of registered agents."""
    return AgentDiscoveryService(
        registered_agents={"coder-agent", "reviewer-agent", "validator-agent"},
        registered_mcp_servers={"mcp-tools-server", "mcp-search-server"},
        idle_timeout=timedelta(minutes=30),
        unresponsive_timeout=timedelta(hours=2),
    )


@pytest.fixture
def empty_discovery_service() -> AgentDiscoveryService:
    """Create a discovery service with no registered agents."""
    return AgentDiscoveryService(
        registered_agents=set(),
        registered_mcp_servers=set(),
    )


@pytest.fixture
def shadow_detector(discovery_service) -> ShadowDetector:
    """Create a shadow detector backed by the discovery service fixture."""
    return ShadowDetector(
        discovery=discovery_service,
        critical_tools={"deploy_to_production", "modify_iam_policy", "delete_resource"},
        dangerous_tools={"execute_code", "write_file", "create_sandbox"},
        monitoring_tools={"read_logs", "query_database"},
        auto_quarantine_threshold=ShadowAlertSeverity.CRITICAL,
    )


@pytest.fixture
def topology_builder() -> AgentTopologyBuilder:
    """Create a fresh topology builder."""
    return AgentTopologyBuilder(use_mock=True)


@pytest.fixture
def populated_discovery(discovery_service) -> AgentDiscoveryService:
    """Create a discovery service pre-populated with agent and MCP records."""
    # Registered agents
    discovery_service.record_agent_activity(
        agent_id="coder-agent",
        agent_type="coder",
        tools_used=["semantic_search", "write_file"],
        mcp_servers_used=["mcp-tools-server"],
        llm_endpoints_used=["bedrock-claude"],
    )
    discovery_service.record_agent_activity(
        agent_id="reviewer-agent",
        agent_type="reviewer",
        tools_used=["read_logs"],
    )

    # Shadow agent
    discovery_service.record_agent_activity(
        agent_id="rogue-agent",
        agent_type="unknown",
        tools_used=["execute_code"],
    )

    # MCP servers
    discovery_service.record_mcp_server(
        server_id="mcp-tools-server",
        server_name="Tools Server",
        endpoint="http://mcp-tools:8080",
        tools_provided=["semantic_search", "code_search"],
    )
    discovery_service.record_mcp_server(
        server_id="shadow-mcp",
        server_name="Unknown Server",
        endpoint="http://unknown:9999",
        tools_provided=["exfiltrate_data"],
    )
    return discovery_service
