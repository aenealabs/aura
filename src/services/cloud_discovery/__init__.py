"""
Cloud Discovery Service Package
================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

This package provides cloud resource discovery capabilities for the
Documentation Agent, enabling correlation between code and actual
deployed infrastructure.

Components:
- CloudDiscoveryService: Main orchestration service
- AWSDiscoveryProvider: AWS resource discovery
- AzureDiscoveryProvider: Azure resource discovery (planned)
- CredentialProxyService: Secure credential management
- CircuitBreaker: Fault tolerance for provider calls
- IaCCorrelator: Code-to-infrastructure correlation
"""

from src.services.cloud_discovery.aws_provider import AWSDiscoveryProvider
from src.services.cloud_discovery.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker,
    get_circuit_breaker_registry,
)
from src.services.cloud_discovery.credential_proxy import (
    AuthenticatedSession,
    CloudCredentialConfig,
    CredentialProxyService,
    CredentialType,
)
from src.services.cloud_discovery.discovery_service import (
    CloudDiscoveryService,
    DiscoveryRequest,
    FullDiscoveryResult,
    create_cloud_discovery_service,
)
from src.services.cloud_discovery.exceptions import (
    CircuitOpenError,
    CloudDiscoveryError,
    CorrelationError,
    CredentialError,
    CrossAccountError,
    DiscoveryTimeoutError,
    GovCloudUnavailableError,
    IaCParseError,
    ProviderError,
    RateLimitError,
)
from src.services.cloud_discovery.iac_correlator import IaCCorrelator, IaCResource
from src.services.cloud_discovery.types import (
    CloudProvider,
    CloudResource,
    CloudResourceType,
    CorrelationResult,
    DiscoveryResult,
    DiscoveryScope,
    IaCMapping,
    RelationshipType,
    ResourceRelationship,
)

__all__ = [
    # Types
    "CloudProvider",
    "CloudResource",
    "CloudResourceType",
    "DiscoveryScope",
    "DiscoveryResult",
    "RelationshipType",
    "ResourceRelationship",
    "IaCMapping",
    "CorrelationResult",
    # Exceptions
    "CloudDiscoveryError",
    "CredentialError",
    "ProviderError",
    "RateLimitError",
    "CircuitOpenError",
    "DiscoveryTimeoutError",
    "GovCloudUnavailableError",
    "CrossAccountError",
    "IaCParseError",
    "CorrelationError",
    # Credential Proxy
    "CredentialProxyService",
    "CredentialType",
    "CloudCredentialConfig",
    "AuthenticatedSession",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "CircuitState",
    "get_circuit_breaker",
    "get_circuit_breaker_registry",
    # Providers
    "AWSDiscoveryProvider",
    # IaC Correlation
    "IaCCorrelator",
    "IaCResource",
    # Main Service
    "CloudDiscoveryService",
    "DiscoveryRequest",
    "FullDiscoveryResult",
    "create_cloud_discovery_service",
]
