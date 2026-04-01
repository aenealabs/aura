"""
Project Aura - AWS Provider Implementations

AWS-specific service implementations wrapping existing services.
Supports both AWS Commercial and AWS GovCloud regions.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter
from src.services.providers.aws.neptune_adapter import NeptuneGraphAdapter
from src.services.providers.aws.opensearch_adapter import OpenSearchVectorAdapter
from src.services.providers.aws.s3_adapter import S3StorageAdapter
from src.services.providers.aws.secrets_manager_adapter import SecretsManagerAdapter

__all__ = [
    "NeptuneGraphAdapter",
    "OpenSearchVectorAdapter",
    "BedrockLLMAdapter",
    "S3StorageAdapter",
    "SecretsManagerAdapter",
]
