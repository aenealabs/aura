"""
Project Aura - Database Connection Factory

Centralized factory for creating database service instances with
environment-aware mode detection. Provides a single entry point
for wiring real AWS connections or mock implementations.

Environment Variables:
    NEPTUNE_ENDPOINT: Neptune cluster endpoint (enables AWS mode)
    OPENSEARCH_ENDPOINT: OpenSearch domain endpoint (enables AWS mode)
    AWS_REGION: AWS region for DynamoDB (enables AWS mode)
    ENVIRONMENT: Environment name (dev, qa, prod)
    PROJECT_NAME: Project name for resource naming

Usage:
    # Individual services
    >>> from src.services.database_connections import get_neptune_service
    >>> neptune = get_neptune_service()

    # All services at once
    >>> from src.services.database_connections import get_database_services
    >>> services = get_database_services()
    >>> neptune = services["neptune"]
    >>> opensearch = services["opensearch"]

Author: Project Aura Team
Created: 2025-11-29
Version: 1.0.0
"""

import logging
import os
from dataclasses import dataclass
from typing import TypedDict

# Import service classes and modes
from src.services.bedrock_llm_service import (
    BedrockLLMService,
    BedrockMode,
    create_llm_service,
)
from src.services.job_persistence_service import (
    JobPersistenceService,
    PersistenceMode,
    create_persistence_service,
)
from src.services.neptune_graph_service import (
    NeptuneGraphService,
    NeptuneMode,
    create_graph_service,
)
from src.services.opensearch_vector_service import (
    OpenSearchMode,
    OpenSearchVectorService,
    create_vector_service,
)
from src.services.titan_embedding_service import (
    EmbeddingMode,
    TitanEmbeddingService,
    create_embedding_service,
)

logger = logging.getLogger(__name__)

# Optional boto3 import for AWS connectivity check
try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.debug("boto3 not available - AWS services will use mock mode")


# Type definitions for service collections
class DatabaseServices(TypedDict):
    """Type definition for database service collection."""

    neptune: NeptuneGraphService
    opensearch: OpenSearchVectorService
    persistence: JobPersistenceService


class AllServices(TypedDict):
    """Type definition for all service collection including LLM/embeddings."""

    neptune: NeptuneGraphService
    opensearch: OpenSearchVectorService
    persistence: JobPersistenceService
    embeddings: TitanEmbeddingService
    llm: BedrockLLMService


@dataclass
class ConnectionStatus:
    """Status of database connections."""

    neptune_mode: str
    opensearch_mode: str
    persistence_mode: str
    embeddings_mode: str
    llm_mode: str
    all_aws: bool
    all_mock: bool


def get_environment() -> str:
    """
    Get current environment name from environment variables.

    Returns:
        Environment name (dev, qa, prod). Defaults to 'dev'.
    """
    return os.environ.get("ENVIRONMENT", "dev")


def get_neptune_service(environment: str | None = None) -> NeptuneGraphService:
    """
    Create Neptune graph service with environment-aware mode detection.

    Mode is determined by:
    - AWS mode: NEPTUNE_ENDPOINT environment variable is set
    - MOCK mode: NEPTUNE_ENDPOINT is not set (default)

    Args:
        environment: Optional environment override (not used, reserved for future)

    Returns:
        Configured NeptuneGraphService instance

    Example:
        >>> neptune = get_neptune_service()
        >>> neptune.add_code_entity("MyClass", "class", "src/app.py", 42)
    """
    service = create_graph_service(environment)
    logger.info(
        f"Neptune service created: mode={service.mode.value}, "
        f"endpoint={service.endpoint}"
    )
    return service


def get_opensearch_service(environment: str | None = None) -> OpenSearchVectorService:
    """
    Create OpenSearch vector service with environment-aware mode detection.

    Mode is determined by:
    - AWS mode: OPENSEARCH_ENDPOINT environment variable is set
    - MOCK mode: OPENSEARCH_ENDPOINT is not set (default)

    Args:
        environment: Optional environment override (not used, reserved for future)

    Returns:
        Configured OpenSearchVectorService instance

    Example:
        >>> opensearch = get_opensearch_service()
        >>> results = opensearch.search_similar(query_vector, k=5)
    """
    service = create_vector_service(environment)
    logger.info(
        f"OpenSearch service created: mode={service.mode.value}, "
        f"endpoint={service.endpoint}"
    )
    return service


def get_persistence_service(environment: str | None = None) -> JobPersistenceService:
    """
    Create DynamoDB persistence service with environment-aware mode detection.

    Mode is determined by:
    - AWS mode: AWS_REGION environment variable is set
    - MOCK mode: AWS_REGION is not set (default)

    Args:
        environment: Optional environment override (not used, reserved for future)

    Returns:
        Configured JobPersistenceService instance

    Example:
        >>> persistence = get_persistence_service()
        >>> persistence.save_job(job)
    """
    service = create_persistence_service(environment)
    logger.info(
        f"Persistence service created: mode={service.mode.value}, "
        f"table={service.table_name}"
    )
    return service


def get_embedding_service(environment: str | None = None) -> TitanEmbeddingService:
    """
    Create Titan embedding service with environment-aware mode detection.

    Mode is determined by:
    - AWS mode: boto3 is available and AWS credentials configured
    - MOCK mode: boto3 not available or credentials missing (default)

    Args:
        environment: Optional environment override (not used, reserved for future)

    Returns:
        Configured TitanEmbeddingService instance

    Example:
        >>> embeddings = get_embedding_service()
        >>> vector = embeddings.generate_embedding("def hello(): pass")
    """
    service = create_embedding_service(environment)
    logger.info(
        f"Embedding service created: mode={service.mode.value}, "
        f"model={service.model_id}"
    )
    return service


def get_llm_service(environment: str | None = None) -> BedrockLLMService:
    """
    Create Bedrock LLM service with environment-aware mode detection.

    Mode is determined by:
    - AWS mode: boto3 is available and AWS credentials configured
    - MOCK mode: boto3 not available or credentials missing (default)

    Args:
        environment: Optional environment override (not used, reserved for future)

    Returns:
        Configured BedrockLLMService instance

    Example:
        >>> llm = get_llm_service()
        >>> response = llm.generate("Analyze this code...")
    """
    service = create_llm_service(environment)
    logger.info(f"LLM service created: mode={service.mode.value}")
    return service


def get_database_services(environment: str | None = None) -> DatabaseServices:
    """
    Create all database services with environment-aware mode detection.

    This is the recommended entry point for API initialization, providing
    all database connections in a single call with consistent configuration.

    Args:
        environment: Optional environment override

    Returns:
        Dictionary containing all database service instances:
        - neptune: NeptuneGraphService
        - opensearch: OpenSearchVectorService
        - persistence: JobPersistenceService

    Example:
        >>> services = get_database_services()
        >>> services["neptune"].add_code_entity(...)
        >>> services["opensearch"].search_similar(...)
        >>> services["persistence"].save_job(...)
    """
    env = environment or get_environment()

    return {
        "neptune": get_neptune_service(env),
        "opensearch": get_opensearch_service(env),
        "persistence": get_persistence_service(env),
    }


def get_all_services(environment: str | None = None) -> AllServices:
    """
    Create all services including LLM and embeddings.

    This provides the complete service stack for full agent functionality.

    Args:
        environment: Optional environment override

    Returns:
        Dictionary containing all service instances:
        - neptune: NeptuneGraphService
        - opensearch: OpenSearchVectorService
        - persistence: JobPersistenceService
        - embeddings: TitanEmbeddingService
        - llm: BedrockLLMService

    Example:
        >>> services = get_all_services()
        >>> vector = services["embeddings"].generate_embedding(code)
        >>> services["opensearch"].index_embedding(doc_id, text, vector)
    """
    env = environment or get_environment()

    return {
        "neptune": get_neptune_service(env),
        "opensearch": get_opensearch_service(env),
        "persistence": get_persistence_service(env),
        "embeddings": get_embedding_service(env),
        "llm": get_llm_service(env),
    }


def check_aws_credentials() -> bool:
    """
    Check if AWS credentials are configured and valid.

    Performs a lightweight STS GetCallerIdentity call to verify:
    - boto3 is available
    - AWS credentials are configured (env vars, config file, or IAM role)
    - Credentials are valid and not expired

    Returns:
        True if credentials are valid, False otherwise

    Note:
        This call is idempotent and has no side effects.
        It's the standard "who am I" check for AWS connectivity.
    """
    if not BOTO3_AVAILABLE:
        logger.debug("AWS credentials check: boto3 not available")
        return False

    try:
        # STS GetCallerIdentity is the canonical credential validation call
        # It works with any valid credentials and doesn't require specific permissions
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        logger.debug(
            f"AWS credentials valid: account={identity.get('Account')}, "
            f"arn={identity.get('Arn')}"
        )
        return True
    except NoCredentialsError:
        logger.debug("AWS credentials check: no credentials found")
        return False
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.debug(f"AWS credentials check failed: {error_code}")
        return False
    except BotoCoreError as e:
        logger.debug(f"AWS credentials check failed: {e}")
        return False
    except Exception as e:
        # Catch any unexpected errors to prevent health check failures
        logger.warning(f"Unexpected error during AWS credentials check: {e}")
        return False


# Cache the credentials check result to avoid repeated STS calls
_aws_credentials_valid: bool | None = None


def get_aws_credentials_status(force_refresh: bool = False) -> bool:
    """
    Get cached AWS credentials status, with optional refresh.

    Args:
        force_refresh: If True, re-check credentials even if cached

    Returns:
        True if AWS credentials are valid, False otherwise
    """
    global _aws_credentials_valid

    if _aws_credentials_valid is None or force_refresh:
        _aws_credentials_valid = check_aws_credentials()

    return _aws_credentials_valid


def clear_credentials_cache() -> None:
    """Clear the cached credentials status. Useful for testing."""
    global _aws_credentials_valid
    _aws_credentials_valid = None


def get_connection_status(verify_credentials: bool = True) -> ConnectionStatus:
    """
    Get current connection status for all services.

    Useful for health checks and debugging connection issues.

    Args:
        verify_credentials: If True, perform actual AWS credential check.
                          If False, only check environment variables (faster).

    Returns:
        ConnectionStatus with mode information for each service

    Example:
        >>> status = get_connection_status()
        >>> print(f"Neptune: {status.neptune_mode}")
        >>> print(f"All AWS: {status.all_aws}")
    """
    # Check environment variables to determine expected modes
    neptune_mode = "aws" if os.environ.get("NEPTUNE_ENDPOINT") else "mock"
    opensearch_mode = "aws" if os.environ.get("OPENSEARCH_ENDPOINT") else "mock"
    persistence_mode = "aws" if os.environ.get("AWS_REGION") else "mock"

    # Embeddings and LLM depend on boto3 AND valid AWS credentials
    if verify_credentials:
        has_aws_credentials = get_aws_credentials_status()
    else:
        # Fast path: just check if boto3 is available and region is set
        has_aws_credentials = BOTO3_AVAILABLE and bool(os.environ.get("AWS_REGION"))

    embeddings_mode = "aws" if has_aws_credentials else "mock"
    llm_mode = "aws" if has_aws_credentials else "mock"

    all_aws = all(
        mode == "aws"
        for mode in [
            neptune_mode,
            opensearch_mode,
            persistence_mode,
            embeddings_mode,
            llm_mode,
        ]
    )

    all_mock = all(
        mode == "mock"
        for mode in [
            neptune_mode,
            opensearch_mode,
            persistence_mode,
            embeddings_mode,
            llm_mode,
        ]
    )

    return ConnectionStatus(
        neptune_mode=neptune_mode,
        opensearch_mode=opensearch_mode,
        persistence_mode=persistence_mode,
        embeddings_mode=embeddings_mode,
        llm_mode=llm_mode,
        all_aws=all_aws,
        all_mock=all_mock,
    )


def print_connection_status() -> None:
    """
    Print human-readable connection status to logger.

    Useful for startup diagnostics.
    """
    status = get_connection_status()

    logger.info("=" * 60)
    logger.info("Database Connection Status")
    logger.info("=" * 60)
    logger.info(f"  Neptune:     {status.neptune_mode.upper()}")
    logger.info(f"  OpenSearch:  {status.opensearch_mode.upper()}")
    logger.info(f"  DynamoDB:    {status.persistence_mode.upper()}")
    logger.info(f"  Embeddings:  {status.embeddings_mode.upper()}")
    logger.info(f"  LLM:         {status.llm_mode.upper()}")
    logger.info("-" * 60)

    if status.all_aws:
        logger.info("  Status: ALL SERVICES CONNECTED TO AWS")
    elif status.all_mock:
        logger.info("  Status: ALL SERVICES IN MOCK MODE")
    else:
        logger.info("  Status: MIXED MODE (some AWS, some mock)")

    logger.info("=" * 60)


# Export convenience aliases
__all__ = [
    # Individual service factories
    "get_neptune_service",
    "get_opensearch_service",
    "get_persistence_service",
    "get_embedding_service",
    "get_llm_service",
    # Batch service factories
    "get_database_services",
    "get_all_services",
    # Status utilities
    "get_connection_status",
    "print_connection_status",
    "get_environment",
    # AWS credential utilities
    "check_aws_credentials",
    "get_aws_credentials_status",
    "clear_credentials_cache",
    "BOTO3_AVAILABLE",
    # Type definitions
    "DatabaseServices",
    "AllServices",
    "ConnectionStatus",
    # Re-exported mode enums for convenience
    "NeptuneMode",
    "OpenSearchMode",
    "PersistenceMode",
    "EmbeddingMode",
    "BedrockMode",
]
