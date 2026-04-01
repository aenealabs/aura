"""
Project Aura - Neo4j Graph Adapter

Adapter for Neo4j graph database implementing GraphDatabaseService interface.
Uses native Cypher queries for optimal performance in self-hosted deployments.

See ADR-049: Self-Hosted Deployment Strategy
See QUERY_LANGUAGE_STRATEGY.md: Native Cypher decision

Environment Variables:
    NEO4J_URI: Connection URI (default: bolt://localhost:7687)
    NEO4J_USERNAME: Username (default: neo4j)
    NEO4J_PASSWORD: Password (required)
    NEO4J_DATABASE: Database name (default: neo4j)
    NEO4J_ENCRYPTED: Enable TLS (default: true for production)
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

from src.abstractions.graph_database import (
    EntityType,
    GraphDatabaseService,
    GraphEntity,
    GraphQueryResult,
    GraphRelationship,
    RelationshipType,
)

logger = logging.getLogger(__name__)

# Lazy import neo4j to avoid import errors when not installed
_neo4j_driver = None


def _get_neo4j():
    """Lazy import neo4j driver."""
    global _neo4j_driver
    if _neo4j_driver is None:
        try:
            import neo4j

            _neo4j_driver = neo4j
        except ImportError:
            raise ImportError(
                "neo4j package not installed. Install with: pip install neo4j"
            )
    return _neo4j_driver


class Neo4jGraphAdapter(GraphDatabaseService):
    """
    Neo4j adapter implementing GraphDatabaseService interface.

    Uses native Cypher queries for all graph operations.
    Supports both local and remote Neo4j instances with TLS.
    """

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
        encrypted: bool | None = None,
    ):
        """
        Initialize Neo4j adapter.

        Args:
            uri: Neo4j connection URI (bolt:// or neo4j://)
            username: Neo4j username
            password: Neo4j password
            database: Database name
            encrypted: Enable TLS encryption
        """
        self.uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD", "")
        self.database = database or os.environ.get("NEO4J_DATABASE", "neo4j")

        # Default to encrypted in production
        if encrypted is None:
            encrypted_str = os.environ.get("NEO4J_ENCRYPTED", "true")
            encrypted = encrypted_str.lower() in ("true", "1", "yes")
        self.encrypted = encrypted

        self._driver = None
        self._connected = False

    def _get_driver(self):
        """Get or create Neo4j driver."""
        if self._driver is None:
            neo4j = _get_neo4j()
            self._driver = neo4j.GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                encrypted=self.encrypted,
            )
        return self._driver

    async def connect(self) -> bool:
        """Establish connection to Neo4j."""
        try:
            driver = self._get_driver()
            # Verify connectivity
            driver.verify_connectivity()
            self._connected = True
            logger.info(f"Neo4j adapter connected to {self.uri}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
        self._connected = False
        logger.info("Neo4j adapter disconnected")

    async def is_connected(self) -> bool:
        """Check if connected."""
        if not self._connected or not self._driver:
            return False
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            self._connected = False
            return False

    def _run_query(self, query: str, parameters: dict[str, Any] | None = None) -> list:
        """Execute a Cypher query and return results."""
        driver = self._get_driver()
        with driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return list(result)

    def _run_write(self, query: str, parameters: dict[str, Any] | None = None) -> Any:
        """Execute a write transaction."""
        driver = self._get_driver()
        with driver.session(database=self.database) as session:
            result = session.execute_write(
                lambda tx: tx.run(query, parameters or {}).single()
            )
            return result

    async def add_entity(self, entity: GraphEntity) -> str:
        """Add a code entity to the graph."""
        query = """
        MERGE (e:CodeEntity {id: $id})
        SET e.entity_type = $entity_type,
            e.name = $name,
            e.repository = $repository,
            e.file_path = $file_path,
            e.properties = $properties,
            e.created_at = $created_at,
            e.updated_at = $updated_at
        RETURN e.id AS id
        """
        now = datetime.now(timezone.utc).isoformat()
        params = {
            "id": entity.id,
            "entity_type": entity.entity_type.value,
            "name": entity.name,
            "repository": entity.repository,
            "file_path": entity.file_path,
            "properties": str(entity.properties),  # Neo4j doesn't support nested maps
            "created_at": entity.created_at.isoformat() if entity.created_at else now,
            "updated_at": now,
        }

        self._run_write(query, params)
        logger.debug(f"Added entity: {entity.id}")
        return entity.id

    async def get_entity(self, entity_id: str) -> GraphEntity | None:
        """Get an entity by ID."""
        query = """
        MATCH (e:CodeEntity {id: $id})
        RETURN e
        """
        results = self._run_query(query, {"id": entity_id})
        if not results:
            return None

        node = results[0]["e"]
        return self._node_to_entity(node)

    def _node_to_entity(self, node) -> GraphEntity:
        """Convert Neo4j node to GraphEntity."""
        import json

        props = node.get("properties", "{}")
        if isinstance(props, str):
            try:
                props = json.loads(props.replace("'", '"'))
            except json.JSONDecodeError:
                props = {}

        created_at = None
        if node.get("created_at"):
            try:
                created_at = datetime.fromisoformat(node["created_at"])
            except (ValueError, TypeError):
                pass

        updated_at = None
        if node.get("updated_at"):
            try:
                updated_at = datetime.fromisoformat(node["updated_at"])
            except (ValueError, TypeError):
                pass

        return GraphEntity(
            id=node["id"],
            entity_type=EntityType(node.get("entity_type", "file")),
            name=node.get("name", ""),
            repository=node.get("repository", ""),
            file_path=node.get("file_path", ""),
            properties=props,
            created_at=created_at,
            updated_at=updated_at,
        )

    async def update_entity(self, entity: GraphEntity) -> bool:
        """Update an existing entity."""
        query = """
        MATCH (e:CodeEntity {id: $id})
        SET e.entity_type = $entity_type,
            e.name = $name,
            e.repository = $repository,
            e.file_path = $file_path,
            e.properties = $properties,
            e.updated_at = $updated_at
        RETURN e.id AS id
        """
        now = datetime.now(timezone.utc).isoformat()
        params = {
            "id": entity.id,
            "entity_type": entity.entity_type.value,
            "name": entity.name,
            "repository": entity.repository,
            "file_path": entity.file_path,
            "properties": str(entity.properties),
            "updated_at": now,
        }

        result = self._run_write(query, params)
        return result is not None

    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and its relationships."""
        query = """
        MATCH (e:CodeEntity {id: $id})
        DETACH DELETE e
        RETURN count(e) AS deleted
        """
        result = self._run_write(query, {"id": entity_id})
        deleted = result["deleted"] if result else 0
        return deleted > 0

    async def add_relationship(self, relationship: GraphRelationship) -> str:
        """Add a relationship between entities."""
        # Neo4j requires relationship types to be identifiers, not parameterized
        # We use a generic RELATES_TO and store the actual type as a property
        query = """
        MATCH (source:CodeEntity {id: $source_id})
        MATCH (target:CodeEntity {id: $target_id})
        MERGE (source)-[r:RELATES_TO {id: $id}]->(target)
        SET r.relationship_type = $relationship_type,
            r.properties = $properties,
            r.weight = $weight
        RETURN r.id AS id
        """
        params = {
            "id": relationship.id,
            "source_id": relationship.source_id,
            "target_id": relationship.target_id,
            "relationship_type": relationship.relationship_type.value,
            "properties": str(relationship.properties),
            "weight": relationship.weight,
        }

        self._run_write(query, params)
        logger.debug(f"Added relationship: {relationship.id}")
        return relationship.id

    async def get_relationships(
        self,
        entity_id: str,
        relationship_type: RelationshipType | None = None,
        direction: str = "both",
    ) -> list[GraphRelationship]:
        """Get relationships for an entity."""
        if direction == "out":
            pattern = "(e:CodeEntity {id: $id})-[r:RELATES_TO]->(other)"
        elif direction == "in":
            pattern = "(e:CodeEntity {id: $id})<-[r:RELATES_TO]-(other)"
        else:
            pattern = "(e:CodeEntity {id: $id})-[r:RELATES_TO]-(other)"

        query = f"""
        MATCH {pattern}
        WHERE $rel_type IS NULL OR r.relationship_type = $rel_type
        RETURN r, startNode(r).id AS source_id, endNode(r).id AS target_id
        """
        params = {
            "id": entity_id,
            "rel_type": relationship_type.value if relationship_type else None,
        }

        results = self._run_query(query, params)
        relationships = []
        for record in results:
            rel = record["r"]
            relationships.append(
                GraphRelationship(
                    id=rel.get("id", ""),
                    relationship_type=RelationshipType(
                        rel.get("relationship_type", "references")
                    ),
                    source_id=record["source_id"],
                    target_id=record["target_id"],
                    properties=self._parse_properties(rel.get("properties", "{}")),
                    weight=rel.get("weight", 1.0),
                )
            )
        return relationships

    def _parse_properties(self, props: str | dict) -> dict[str, Any]:
        """Parse properties from Neo4j storage."""
        import json

        if isinstance(props, dict):
            return props
        if isinstance(props, str):
            try:
                return json.loads(props.replace("'", '"'))
            except json.JSONDecodeError:
                return {}
        return {}

    async def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship."""
        query = """
        MATCH ()-[r:RELATES_TO {id: $id}]-()
        DELETE r
        RETURN count(r) AS deleted
        """
        result = self._run_write(query, {"id": relationship_id})
        deleted = result["deleted"] if result else 0
        return deleted > 0

    async def find_related_code(
        self,
        entity_id: str,
        max_depth: int = 2,
        relationship_types: list[RelationshipType] | None = None,
    ) -> GraphQueryResult:
        """Find related code via graph traversal."""
        rel_filter = ""
        if relationship_types:
            types_list = [rt.value for rt in relationship_types]
            rel_filter = f"AND r.relationship_type IN {types_list}"

        query = f"""
        MATCH path = (start:CodeEntity {{id: $id}})-[r:RELATES_TO*1..{max_depth}]-(related:CodeEntity)
        WHERE start <> related {rel_filter}
        RETURN DISTINCT related,
               [rel IN relationships(path) | rel] AS rels
        LIMIT 100
        """
        params = {"id": entity_id}

        results = self._run_query(query, params)

        entities = []
        relationships = []
        seen_entities = set()
        seen_relationships = set()

        for record in results:
            # Add entity
            node = record["related"]
            entity = self._node_to_entity(node)
            if entity.id not in seen_entities:
                entities.append(entity)
                seen_entities.add(entity.id)

            # Add relationships
            for rel in record["rels"]:
                rel_id = rel.get("id", "")
                if rel_id and rel_id not in seen_relationships:
                    relationships.append(
                        GraphRelationship(
                            id=rel_id,
                            relationship_type=RelationshipType(
                                rel.get("relationship_type", "references")
                            ),
                            source_id=entity_id,
                            target_id=entity.id,
                            properties=self._parse_properties(
                                rel.get("properties", "{}")
                            ),
                            weight=rel.get("weight", 1.0),
                        )
                    )
                    seen_relationships.add(rel_id)

        return GraphQueryResult(entities=entities, relationships=relationships)

    async def search_by_name(
        self,
        name_pattern: str,
        entity_types: list[EntityType] | None = None,
        repository: str | None = None,
        limit: int = 100,
    ) -> list[GraphEntity]:
        """Search entities by name pattern."""
        # Build filters
        filters = ["e.name =~ $pattern"]
        if entity_types:
            types_list = [et.value for et in entity_types]
            filters.append(f"e.entity_type IN {types_list}")
        if repository:
            filters.append("e.repository = $repository")

        where_clause = " AND ".join(filters)

        query = f"""
        MATCH (e:CodeEntity)
        WHERE {where_clause}
        RETURN e
        LIMIT $limit
        """
        # Convert SQL-like wildcards to regex
        regex_pattern = name_pattern.replace("%", ".*").replace("_", ".")
        if not regex_pattern.startswith(".*"):
            regex_pattern = ".*" + regex_pattern
        if not regex_pattern.endswith(".*"):
            regex_pattern = regex_pattern + ".*"

        params = {
            "pattern": f"(?i){regex_pattern}",  # Case-insensitive
            "repository": repository,
            "limit": limit,
        }

        results = self._run_query(query, params)
        return [self._node_to_entity(record["e"]) for record in results]

    async def delete_by_repository(self, repository: str) -> int:
        """Delete all entities for a repository."""
        query = """
        MATCH (e:CodeEntity {repository: $repository})
        DETACH DELETE e
        RETURN count(e) AS deleted
        """
        result = self._run_write(query, {"repository": repository})
        deleted = result["deleted"] if result else 0
        logger.info(f"Deleted {deleted} entities for repository: {repository}")
        return deleted

    async def delete_by_file_path(self, file_path: str, repository: str) -> int:
        """Delete entities for a file."""
        query = """
        MATCH (e:CodeEntity {file_path: $file_path, repository: $repository})
        DETACH DELETE e
        RETURN count(e) AS deleted
        """
        result = self._run_write(
            query, {"file_path": file_path, "repository": repository}
        )
        deleted = result["deleted"] if result else 0
        logger.info(f"Deleted {deleted} entities for file: {file_path}")
        return deleted

    async def get_health(self) -> dict[str, Any]:
        """Get Neo4j health status."""
        try:
            if await self.is_connected():
                # Get server info
                driver = self._get_driver()
                with driver.session(database=self.database) as session:
                    result = session.run("CALL dbms.components()")
                    components = list(result)

                    version = "unknown"
                    if components:
                        version = components[0].get("version", "unknown")

                return {
                    "status": "healthy",
                    "connected": True,
                    "uri": self.uri,
                    "database": self.database,
                    "version": version,
                    "encrypted": self.encrypted,
                }
            else:
                return {
                    "status": "disconnected",
                    "connected": False,
                    "uri": self.uri,
                    "database": self.database,
                }
        except Exception as e:
            return {
                "status": "error",
                "connected": False,
                "error": str(e),
                "uri": self.uri,
            }

    async def get_statistics(self) -> dict[str, Any]:
        """Get graph statistics."""
        try:
            entity_query = "MATCH (e:CodeEntity) RETURN count(e) AS count"
            rel_query = "MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS count"

            entity_result = self._run_query(entity_query)
            rel_result = self._run_query(rel_query)

            entity_count = entity_result[0]["count"] if entity_result else 0
            rel_count = rel_result[0]["count"] if rel_result else 0

            # Get entity type distribution
            type_query = """
            MATCH (e:CodeEntity)
            RETURN e.entity_type AS type, count(e) AS count
            """
            type_results = self._run_query(type_query)
            type_distribution = {
                record["type"]: record["count"] for record in type_results
            }

            return {
                "entity_count": entity_count,
                "relationship_count": rel_count,
                "entity_types": type_distribution,
                "database": self.database,
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {
                "entity_count": "unknown",
                "relationship_count": "unknown",
                "error": str(e),
            }
