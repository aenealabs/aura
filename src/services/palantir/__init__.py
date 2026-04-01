"""
Project Aura - Palantir AIP Integration Service

Implements ADR-074: Palantir AIP Integration for Data-Informed Code Security

This module provides bidirectional integration between Aura and Palantir AIP:
- Ontology Bridge: Syncs threat intelligence and asset data from Palantir
- Event Publisher: Publishes remediation events to Palantir Foundry
- Enterprise Adapter: Abstract interface for future platform integrations

Components:
- EnterpriseDataPlatformAdapter: Abstract base for data platform integrations
- PalantirAIPAdapter: Palantir-specific implementation
- OntologyBridgeService: Synchronizes Palantir Ontology objects
- PalantirEventPublisher: Publishes Aura events to Palantir
- PalantirCircuitBreaker: Resilience pattern with fallback

Usage:
    >>> from src.services.palantir import PalantirAIPAdapter, OntologyBridgeService
    >>> adapter = PalantirAIPAdapter(
    ...     ontology_api_url="https://org.palantirfoundry.com/ontology",
    ...     foundry_api_url="https://org.palantirfoundry.com/foundry",
    ...     api_key="your-api-key",
    ... )
    >>> threat_context = await adapter.get_threat_context(["CVE-2024-1234"])
"""

from src.services.palantir.base_adapter import (
    ConnectorResult,
    ConnectorStatus,
    EnterpriseDataPlatformAdapter,
)
from src.services.palantir.circuit_breaker import (
    PALANTIR_CIRCUIT_CONFIG,
    PalantirCircuitBreaker,
)
from src.services.palantir.event_publisher import PalantirEventPublisher
from src.services.palantir.ontology_bridge import OntologyBridgeService
from src.services.palantir.palantir_adapter import PalantirAIPAdapter
from src.services.palantir.types import (
    AssetContext,
    BatchResult,
    ConflictResolutionStrategy,
    DataClassification,
    PalantirConfig,
    PalantirObjectType,
    RemediationEvent,
    RemediationEventType,
    SyncResult,
    SyncStatus,
    ThreatContext,
)

__all__ = [
    # Types
    "ThreatContext",
    "AssetContext",
    "RemediationEvent",
    "RemediationEventType",
    "PalantirObjectType",
    "SyncStatus",
    "SyncResult",
    "BatchResult",
    "PalantirConfig",
    "DataClassification",
    "ConflictResolutionStrategy",
    # Base adapter
    "ConnectorStatus",
    "ConnectorResult",
    "EnterpriseDataPlatformAdapter",
    # Palantir adapter
    "PalantirAIPAdapter",
    # Services
    "OntologyBridgeService",
    "PalantirEventPublisher",
    # Circuit breaker
    "PALANTIR_CIRCUIT_CONFIG",
    "PalantirCircuitBreaker",
]
