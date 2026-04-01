"""
Project Aura - Agent Traffic Interceptor

Real-time capture of all agent-to-agent, agent-to-tool, and agent-to-LLM
traffic for runtime security monitoring and behavioral analysis.

Based on ADR-083: Runtime Agent Security Platform
"""

from .protocol import (
    InterceptionPoint,
    TrafficBatch,
    TrafficDirection,
    TrafficEvent,
    TrafficEventType,
    TrafficFilter,
    TrafficSummary,
)
from .storage import TrafficStorageAdapter, get_traffic_storage, reset_traffic_storage
from .traffic_interceptor import (
    AgentTrafficInterceptor,
    get_traffic_interceptor,
    reset_traffic_interceptor,
)

__all__ = [
    # Protocol
    "InterceptionPoint",
    "TrafficDirection",
    "TrafficEventType",
    "TrafficEvent",
    "TrafficBatch",
    "TrafficFilter",
    "TrafficSummary",
    # Interceptor
    "AgentTrafficInterceptor",
    "get_traffic_interceptor",
    "reset_traffic_interceptor",
    # Storage
    "TrafficStorageAdapter",
    "get_traffic_storage",
    "reset_traffic_storage",
]
