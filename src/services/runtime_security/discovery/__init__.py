"""
Project Aura - Agent Discovery Service

Continuous inventory of all agents, MCP servers, tool registrations,
and LLM endpoints with shadow agent detection.

Extended by ADR-086 with lifecycle state machine, credential
enumerators, decommission verification, ghost agent scanning,
and attestation.

Based on ADR-083: Runtime Agent Security Platform
"""

from .agent_discovery import (
    AgentDiscoveryService,
    get_agent_discovery,
    reset_agent_discovery,
)
from .attestation import AttestationService, AttestationStatus, DecommissionAttestation
from .decommission_verifier import DecommissionReport, DecommissionVerifier
from .ghost_agent_scanner import (
    GhostAgentFinding,
    GhostAgentScanner,
    GhostFindingSeverity,
    ScanResult,
)
from .lifecycle_state_machine import (
    AgentLifecycleRecord,
    DecommissionTrigger,
    InvalidTransitionError,
    LifecycleState,
    LifecycleStateMachine,
    LifecycleTransition,
    get_lifecycle_state_machine,
    reset_lifecycle_state_machine,
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
    # ADR-086: Lifecycle State Machine
    "LifecycleState",
    "DecommissionTrigger",
    "LifecycleTransition",
    "AgentLifecycleRecord",
    "InvalidTransitionError",
    "LifecycleStateMachine",
    "get_lifecycle_state_machine",
    "reset_lifecycle_state_machine",
    # ADR-086: Attestation
    "AttestationStatus",
    "DecommissionAttestation",
    "AttestationService",
    # ADR-086: Decommission Verifier
    "DecommissionReport",
    "DecommissionVerifier",
    # ADR-086: Ghost Agent Scanner
    "GhostFindingSeverity",
    "GhostAgentFinding",
    "ScanResult",
    "GhostAgentScanner",
]
