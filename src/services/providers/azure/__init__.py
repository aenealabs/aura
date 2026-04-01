"""
Project Aura - Azure Provider Implementations

Azure-specific service implementations for Azure Government deployment.
Supports both Azure Commercial and Azure Government regions.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

from src.services.providers.azure.azure_ai_search_service import AzureAISearchService
from src.services.providers.azure.azure_blob_service import AzureBlobService
from src.services.providers.azure.azure_keyvault_service import AzureKeyVaultService
from src.services.providers.azure.azure_openai_service import AzureOpenAIService
from src.services.providers.azure.cosmos_graph_service import CosmosDBGraphService

__all__ = [
    "CosmosDBGraphService",
    "AzureAISearchService",
    "AzureOpenAIService",
    "AzureBlobService",
    "AzureKeyVaultService",
]
