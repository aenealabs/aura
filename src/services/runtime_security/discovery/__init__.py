"""
Project Aura - Agent Discovery Service

Continuous inventory of all agents, MCP servers, tool registrations,
and LLM endpoints with shadow agent detection.

Based on ADR-083: Runtime Agent Security Platform
"""

from .agent_discovery import (
    AgentDiscoveryService,
    get_agent_discovery,
    reset_agent_discovery,
)
from .shadow_detector import ShadowAlert, ShadowAlertSeverity, ShadowDetector
from .topology import AgentTopologyBuilder, TopologyEdge, TopologyNode, TopologySnapshot

__all__ = [
    # Discovery
    "AgentDiscoveryService",
    "get_agent_discovery",
    "reset_agent_discovery",
    # Shadow Detection
    "ShadowDetector",
    "ShadowAlert",
    "ShadowAlertSeverity",
    # Topology
    "AgentTopologyBuilder",
    "TopologyNode",
    "TopologyEdge",
    "TopologySnapshot",
]
