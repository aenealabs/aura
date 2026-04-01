"""
Project Aura - Migration Toolkit

Tools for migrating from AWS services to self-hosted alternatives.
Supports migration from:
- Neptune → Neo4j (graph database)
- DynamoDB → PostgreSQL (document storage)
- S3 → MinIO (object storage)
- Secrets Manager → File-based secrets

See ADR-049: Self-Hosted Deployment Strategy
"""

from src.migration.base import (
    MigrationConfig,
    MigrationError,
    MigrationProgress,
    MigrationResult,
    MigrationStatus,
)

__all__ = [
    "MigrationConfig",
    "MigrationError",
    "MigrationProgress",
    "MigrationResult",
    "MigrationStatus",
]
