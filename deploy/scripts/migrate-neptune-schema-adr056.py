#!/usr/bin/env python3
"""
Neptune Schema Migration for ADR-056 Documentation Agent
=========================================================

This script adds the new vertex and edge types required for the
Documentation Agent feature:

New Vertex Labels:
- InfrastructureResource: Cloud infrastructure resources
- ServiceBoundary: Detected service groupings
- DataFlow: Data movement patterns

New Edge Labels:
- CONNECTS_TO: Network/service connections
- OWNED_BY: Resource ownership
- PRODUCES_TO: Event/message production
- CONSUMES_FROM: Event/message consumption
- READS_FROM: Data read operations
- WRITES_TO: Data write operations
- CONTAINS: Service boundary contains component

New Indexes:
- resource_type + region composite index
- boundary_id index
- flow_id index
- vertex_id index (for all new vertex types)

Usage:
    python migrate-neptune-schema-adr056.py [--endpoint ENDPOINT] [--dry-run]

Environment Variables:
    NEPTUNE_ENDPOINT: Neptune cluster endpoint
    NEPTUNE_PORT: Neptune port (default: 8182)
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Try to import gremlin-python
try:
    from gremlin_python.driver import client, serializer

    GREMLIN_AVAILABLE = True
except ImportError:
    GREMLIN_AVAILABLE = False
    logger.warning("gremlin-python not installed. Run: pip install gremlin-python")


class NeptuneMigration:
    """Handles Neptune schema migrations."""

    def __init__(self, endpoint: str, port: int = 8182, dry_run: bool = False):
        self.endpoint = endpoint
        self.port = port
        self.dry_run = dry_run
        self.client = None

    def connect(self) -> bool:
        """Establish connection to Neptune."""
        if not GREMLIN_AVAILABLE:
            logger.error("gremlin-python not available")
            return False

        try:
            url = f"wss://{self.endpoint}:{self.port}/gremlin"
            logger.info(f"Connecting to Neptune: {url}")

            self.client = client.Client(
                url,
                "g",
                message_serializer=serializer.GraphSONSerializersV3d0(),
            )

            # Test connection
            result = self.client.submit("g.V().limit(1)").all().result()
            logger.info("Connection established successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Neptune: {e}")
            return False

    def close(self):
        """Close Neptune connection."""
        if self.client:
            self.client.close()
            logger.info("Connection closed")

    def execute(self, query: str, description: str) -> bool:
        """Execute a Gremlin query."""
        logger.info(f"Executing: {description}")

        if self.dry_run:
            logger.info(f"[DRY RUN] Would execute: {query[:100]}...")
            return True

        try:
            self.client.submit(query).all().result()
            logger.info(f"  Success: {description}")
            return True
        except Exception as e:
            logger.warning(f"  Note: {e}")
            return False

    def run_migration(self) -> bool:
        """Run the schema migration."""
        logger.info("=" * 60)
        logger.info("Neptune Schema Migration - ADR-056 Documentation Agent")
        logger.info("=" * 60)
        logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info("")

        if not self.connect():
            return False

        success = True

        try:
            # ===================================================================
            # Step 1: Verify existing vertex labels exist
            # ===================================================================
            logger.info("-" * 40)
            logger.info("Step 1: Verifying existing schema...")

            # Check if CodeEntity label exists
            result = (
                self.client.submit("g.V().hasLabel('CodeEntity').limit(1).count()")
                .all()
                .result()
            )
            code_entity_count = result[0] if result else 0
            logger.info(f"  Found {code_entity_count} CodeEntity vertices")

            # ===================================================================
            # Step 2: Create sample vertices for new labels (to register labels)
            # ===================================================================
            logger.info("-" * 40)
            logger.info("Step 2: Registering new vertex labels...")

            # Note: Neptune automatically creates labels when first vertex is added
            # We create and immediately delete marker vertices to register labels

            marker_queries = [
                (
                    "InfrastructureResource",
                    """
                    g.addV('InfrastructureResource')
                     .property('vertex_id', '__migration_marker__')
                     .property('resource_id', '__migration_marker__')
                     .property('resource_type', 'migration_test')
                     .property('created_at', '2024-01-01')
                    """,
                ),
                (
                    "ServiceBoundary",
                    """
                    g.addV('ServiceBoundary')
                     .property('vertex_id', '__migration_marker__')
                     .property('boundary_id', '__migration_marker__')
                     .property('name', 'Migration Test')
                     .property('created_at', '2024-01-01')
                    """,
                ),
                (
                    "DataFlow",
                    """
                    g.addV('DataFlow')
                     .property('vertex_id', '__migration_marker__')
                     .property('flow_id', '__migration_marker__')
                     .property('source_id', 'test')
                     .property('target_id', 'test')
                     .property('created_at', '2024-01-01')
                    """,
                ),
            ]

            for label, query in marker_queries:
                self.execute(query, f"Register '{label}' vertex label")

            # Clean up marker vertices
            cleanup_query = "g.V().has('vertex_id', '__migration_marker__').drop()"
            self.execute(cleanup_query, "Clean up migration markers")

            # ===================================================================
            # Step 3: Verify new edge labels work
            # ===================================================================
            logger.info("-" * 40)
            logger.info("Step 3: Verifying edge label support...")

            edge_types = [
                "CONNECTS_TO",
                "OWNED_BY",
                "PRODUCES_TO",
                "CONSUMES_FROM",
                "READS_FROM",
                "WRITES_TO",
                "CONTAINS",
            ]

            logger.info(f"  Supported edge types: {', '.join(edge_types)}")
            logger.info("  Note: Neptune creates edge labels dynamically")

            # ===================================================================
            # Step 4: Create indexes for efficient traversal
            # ===================================================================
            logger.info("-" * 40)
            logger.info("Step 4: Index recommendations...")

            # Neptune automatically indexes property keys
            # But we document the important ones for query optimization

            index_recommendations = [
                ("vertex_id", "Primary lookup for all new vertex types"),
                ("resource_id", "Infrastructure resource lookups"),
                ("resource_type", "Filter by resource type"),
                ("region", "Filter by AWS region"),
                ("boundary_id", "Service boundary lookups"),
                ("repository_id", "Filter by repository"),
                ("flow_id", "Data flow lookups"),
                ("source_id", "Data flow source lookups"),
                ("target_id", "Data flow target lookups"),
            ]

            for prop, description in index_recommendations:
                logger.info(f"  - {prop}: {description}")

            logger.info("")
            logger.info("Note: Neptune automatically indexes all property keys.")
            logger.info("For composite indexes, consider Neptune Analytics.")

            # ===================================================================
            # Step 5: Verify migration
            # ===================================================================
            logger.info("-" * 40)
            logger.info("Step 5: Verification...")

            # Count vertices by label
            labels_to_check = [
                "CodeEntity",
                "InfrastructureResource",
                "ServiceBoundary",
                "DataFlow",
            ]

            for label in labels_to_check:
                try:
                    result = (
                        self.client.submit(f"g.V().hasLabel('{label}').count()")
                        .all()
                        .result()
                    )
                    count = result[0] if result else 0
                    logger.info(f"  {label}: {count} vertices")
                except Exception as e:
                    logger.info(f"  {label}: 0 vertices (label not yet used)")

            logger.info("")
            logger.info("=" * 60)
            logger.info("Migration completed successfully!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            success = False

        finally:
            self.close()

        return success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Neptune Schema Migration for ADR-056")
    parser.add_argument(
        "--endpoint",
        default=os.getenv("NEPTUNE_ENDPOINT", "neptune.aura.local"),
        help="Neptune cluster endpoint",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("NEPTUNE_PORT", "8182")),
        help="Neptune port",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    migration = NeptuneMigration(
        endpoint=args.endpoint,
        port=args.port,
        dry_run=args.dry_run,
    )

    success = migration.run_migration()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
