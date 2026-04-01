"""
Project Aura - Self-Hosted Provider Implementations

ADR-049: Self-Hosted Deployment Strategy

Provides database and LLM adapters for self-hosted deployments:
- Neo4jGraphAdapter: Graph database (replaces Neptune)
- PostgresDocumentAdapter: Document storage (replaces DynamoDB)
- SelfHostedOpenSearchAdapter: Vector search (self-managed OpenSearch)
- LocalLLMAdapter: LLM inference (vLLM, TGI, Ollama)
- FileSecretsAdapter: Local secrets management

Environment Variables:
    NEO4J_URI: Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_USERNAME: Neo4j username (default: neo4j)
    NEO4J_PASSWORD: Neo4j password
    NEO4J_DATABASE: Neo4j database name (default: neo4j)

    POSTGRES_HOST: PostgreSQL host (default: localhost)
    POSTGRES_PORT: PostgreSQL port (default: 5432)
    POSTGRES_DATABASE: PostgreSQL database (default: aura)
    POSTGRES_USERNAME: PostgreSQL username (default: aura)
    POSTGRES_PASSWORD: PostgreSQL password

    OPENSEARCH_ENDPOINT: OpenSearch endpoint (default: http://localhost:9200)
    OPENSEARCH_USERNAME: OpenSearch username (optional)
    OPENSEARCH_PASSWORD: OpenSearch password (optional)

    LLM_PROVIDER: LLM backend (vllm, tgi, ollama, openai_compatible)
    LLM_ENDPOINT: LLM API endpoint (default: http://localhost:8000/v1)
    LLM_MODEL_ID: Model identifier (default: mistralai/Mistral-7B-Instruct-v0.2)
    LLM_API_KEY: API key for authenticated endpoints (optional)

    SECRETS_PATH: Path for file-based secrets (default: /etc/aura/secrets)
"""

from src.services.providers.self_hosted.file_secrets_adapter import FileSecretsAdapter
from src.services.providers.self_hosted.local_llm_adapter import LocalLLMAdapter
from src.services.providers.self_hosted.minio_storage_adapter import MinioStorageAdapter
from src.services.providers.self_hosted.neo4j_graph_adapter import Neo4jGraphAdapter
from src.services.providers.self_hosted.postgres_document_adapter import (
    PostgresDocumentAdapter,
)
from src.services.providers.self_hosted.selfhosted_opensearch_adapter import (
    SelfHostedOpenSearchAdapter,
)

__all__ = [
    "Neo4jGraphAdapter",
    "PostgresDocumentAdapter",
    "SelfHostedOpenSearchAdapter",
    "LocalLLMAdapter",
    "FileSecretsAdapter",
    "MinioStorageAdapter",
]
