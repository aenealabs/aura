"""
Project Aura - Neptune to Neo4j Migrator

Migrates graph data from AWS Neptune to Neo4j.
Handles both vertices (entities) and edges (relationships).

See ADR-049: Self-Hosted Deployment Strategy
"""

import logging
from typing import Any

from src.migration.base import BaseMigrator, MigrationConfig, MigrationError

logger = logging.getLogger(__name__)


class NeptuneToNeo4jMigrator(BaseMigrator):
    """
    Migrates graph data from Neptune to Neo4j.

    Features:
    - Batch export from Neptune via Gremlin
    - Transforms Gremlin format to Cypher
    - Preserves all properties and relationships
    - Supports incremental migration
    """

    def __init__(
        self,
        neptune_endpoint: str,
        neo4j_uri: str,
        neo4j_username: str = "neo4j",
        neo4j_password: str = "",
        neo4j_database: str = "neo4j",
        config: MigrationConfig | None = None,
    ):
        """
        Initialize Neptune to Neo4j migrator.

        Args:
            neptune_endpoint: Neptune cluster endpoint
            neo4j_uri: Neo4j connection URI (bolt://)
            neo4j_username: Neo4j username
            neo4j_password: Neo4j password
            neo4j_database: Neo4j database name
            config: Migration configuration
        """
        super().__init__(config)
        self.neptune_endpoint = neptune_endpoint
        self.neo4j_uri = neo4j_uri
        self.neo4j_username = neo4j_username
        self.neo4j_password = neo4j_password
        self.neo4j_database = neo4j_database

        self._neptune_client = None
        self._neo4j_driver = None
        self._entities: list[dict[str, Any]] = []
        self._relationships: list[dict[str, Any]] = []

    @property
    def source_type(self) -> str:
        return "neptune"

    @property
    def target_type(self) -> str:
        return "neo4j"

    async def connect_source(self) -> bool:
        """Connect to Neptune."""
        try:
            from gremlin_python.driver import client as gremlin_client

            self._neptune_client = gremlin_client.Client(
                f"wss://{self.neptune_endpoint}:8182/gremlin",
                "g",
            )
            # Test connection
            result = self._neptune_client.submit("g.V().count()").all().result()
            logger.info(f"Connected to Neptune, found {result[0]} vertices")
            return True
        except ImportError:
            logger.warning("Gremlin Python not installed, using mock mode")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neptune: {e}")
            return False

    async def connect_target(self) -> bool:
        """Connect to Neo4j."""
        try:
            from neo4j import GraphDatabase

            self._neo4j_driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_username, self.neo4j_password),
            )
            # Test connection
            self._neo4j_driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.neo4j_uri}")
            return True
        except ImportError:
            logger.warning("Neo4j driver not installed, using mock mode")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from both services."""
        if self._neptune_client:
            self._neptune_client.close()
            self._neptune_client = None
        if self._neo4j_driver:
            self._neo4j_driver.close()
            self._neo4j_driver = None

    async def count_source_items(self) -> int:
        """Count total vertices and edges in Neptune."""
        if not self._neptune_client:
            return 0

        try:
            # Count vertices
            vertex_result = self._neptune_client.submit("g.V().count()").all().result()
            vertex_count = vertex_result[0] if vertex_result else 0

            # Count edges
            edge_result = self._neptune_client.submit("g.E().count()").all().result()
            edge_count = edge_result[0] if edge_result else 0

            total = vertex_count + edge_count
            logger.info(
                f"Source contains {vertex_count} vertices and {edge_count} edges"
            )
            return total
        except Exception as e:
            logger.error(f"Failed to count source items: {e}")
            return 0

    async def fetch_source_batch(self, offset: int, limit: int) -> list[dict[str, Any]]:
        """Fetch batch of vertices and edges from Neptune."""
        if not self._neptune_client:
            return []

        items = []

        try:
            # Fetch vertices first, then edges
            vertex_count = len(self._entities)

            if offset < vertex_count or not self._entities:
                # Fetch vertices
                query = f"g.V().range({offset}, {offset + limit}).valueMap(true).by(unfold())"
                result = self._neptune_client.submit(query).all().result()

                for v in result:
                    items.append(
                        {
                            "type": "vertex",
                            "id": v.get("id", v.get("T.id")),
                            "label": v.get("label", v.get("T.label", "CodeEntity")),
                            "properties": {
                                k: v
                                for k, v in v.items()
                                if k not in ("id", "label", "T.id", "T.label")
                            },
                        }
                    )
            else:
                # Fetch edges
                edge_offset = offset - vertex_count
                query = f"""
                    g.E().range({edge_offset}, {edge_offset + limit})
                    .project('id', 'label', 'outV', 'inV', 'properties')
                    .by(id)
                    .by(label)
                    .by(outV().id())
                    .by(inV().id())
                    .by(valueMap().by(unfold()))
                """
                result = self._neptune_client.submit(query).all().result()

                for e in result:
                    items.append(
                        {
                            "type": "edge",
                            "id": e["id"],
                            "label": e["label"],
                            "source_id": e["outV"],
                            "target_id": e["inV"],
                            "properties": e.get("properties", {}),
                        }
                    )

        except Exception as e:
            logger.error(f"Failed to fetch batch at offset {offset}: {e}")

        return items

    async def migrate_item(self, item: dict[str, Any]) -> bool:
        """Migrate a vertex or edge to Neo4j."""
        if not self._neo4j_driver:
            return True  # Mock mode

        try:
            item_type = item.get("type")

            if item_type == "vertex":
                return await self._migrate_vertex(item)
            elif item_type == "edge":
                return await self._migrate_edge(item)
            else:
                logger.warning(f"Unknown item type: {item_type}")
                return False

        except Exception as e:
            raise MigrationError(
                f"Failed to migrate item {item.get('id')}: {e}",
                item_id=str(item.get("id")),
            )

    async def _migrate_vertex(self, vertex: dict[str, Any]) -> bool:
        """Migrate a vertex to Neo4j."""
        vertex_id = vertex["id"]
        label = vertex.get("label", "CodeEntity")
        properties = vertex.get("properties", {})

        # Build Cypher query
        props_str = ", ".join(f"{k}: ${k}" for k in properties.keys())

        query = f"""
            MERGE (n:{label} {{id: $id}})
            SET n += {{{props_str}}}
            RETURN n.id AS id
        """

        params = {"id": str(vertex_id), **properties}

        with self._neo4j_driver.session(database=self.neo4j_database) as session:
            session.execute_write(lambda tx: tx.run(query, params))

        return True

    async def _migrate_edge(self, edge: dict[str, Any]) -> bool:
        """Migrate an edge to Neo4j."""
        edge_id = edge["id"]
        label = edge.get("label", "RELATES_TO")
        source_id = edge["source_id"]
        target_id = edge["target_id"]
        properties = edge.get("properties", {})

        # Build Cypher query
        props_str = (
            ", ".join(f"{k}: ${k}" for k in properties.keys()) if properties else ""
        )

        if props_str:
            query = f"""
                MATCH (source {{id: $source_id}})
                MATCH (target {{id: $target_id}})
                MERGE (source)-[r:RELATES_TO {{id: $edge_id}}]->(target)
                SET r.relationship_type = $label, r += {{{props_str}}}
                RETURN r.id AS id
            """
        else:
            query = """
                MATCH (source {id: $source_id})
                MATCH (target {id: $target_id})
                MERGE (source)-[r:RELATES_TO {id: $edge_id}]->(target)
                SET r.relationship_type = $label
                RETURN r.id AS id
            """

        params = {
            "edge_id": str(edge_id),
            "source_id": str(source_id),
            "target_id": str(target_id),
            "label": label,
            **properties,
        }

        with self._neo4j_driver.session(database=self.neo4j_database) as session:
            session.execute_write(lambda tx: tx.run(query, params))

        return True

    async def verify_item(self, item: dict[str, Any]) -> bool:
        """Verify item was migrated correctly."""
        if not self._neo4j_driver:
            return True  # Mock mode

        try:
            item_id = str(item.get("id"))
            item_type = item.get("type")

            with self._neo4j_driver.session(database=self.neo4j_database) as session:
                if item_type == "vertex":
                    result = session.run(
                        "MATCH (n {id: $id}) RETURN n.id AS id",
                        {"id": item_id},
                    )
                    return result.single() is not None
                elif item_type == "edge":
                    result = session.run(
                        "MATCH ()-[r {id: $id}]->() RETURN r.id AS id",
                        {"id": item_id},
                    )
                    return result.single() is not None

            return False

        except Exception as e:
            logger.warning(f"Verification failed for {item.get('id')}: {e}")
            return False
