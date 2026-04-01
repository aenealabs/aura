"""
Project Aura - Cloud Abstraction Layer (CAL)

Abstract interfaces for multi-cloud deployment support.
Enables deployment to AWS GovCloud, Azure Government, and other cloud providers.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

from src.abstractions.cloud_provider import CloudProvider, CloudRegion
from src.abstractions.graph_database import (
    GraphDatabaseService,
    GraphEntity,
    GraphRelationship,
)
from src.abstractions.llm_service import (
    LLMRequest,
    LLMResponse,
    LLMService,
    ModelConfig,
)
from src.abstractions.secrets_service import SecretsService
from src.abstractions.storage_service import StorageObject, StorageService
from src.abstractions.vector_database import (
    SearchResult,
    VectorDatabaseService,
    VectorDocument,
)

__all__ = [
    # Cloud Provider
    "CloudProvider",
    "CloudRegion",
    # Graph Database
    "GraphDatabaseService",
    "GraphEntity",
    "GraphRelationship",
    # Vector Database
    "VectorDatabaseService",
    "VectorDocument",
    "SearchResult",
    # LLM Service
    "LLMService",
    "LLMRequest",
    "LLMResponse",
    "ModelConfig",
    # Storage
    "StorageService",
    "StorageObject",
    # Secrets
    "SecretsService",
]
