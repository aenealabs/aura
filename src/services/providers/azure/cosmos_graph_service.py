"""
Project Aura - Azure Cosmos DB Graph Service

Azure Cosmos DB Gremlin API implementation of GraphDatabaseService.
Provides graph database functionality for Azure Government deployments.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

import logging
import os
from typing import TYPE_CHECKING, Any

from src.abstractions.graph_database import (
    EntityType,
    GraphDatabaseService,
    GraphEntity,
    GraphQueryResult,
    GraphRelationship,
    RelationshipType,
)

if TYPE_CHECKING:
    from azure.cosmos import ContainerProxy, DatabaseProxy

logger = logging.getLogger(__name__)

# Optional Azure dependencies
try:
    from azure.cosmos import CosmosClient
    from azure.identity import DefaultAzureCredential

    COSMOS_AVAILABLE = True
except ImportError:
    COSMOS_AVAILABLE = False
    logger.warning("Azure Cosmos DB SDK not available - using mock mode")


class CosmosDBGraphService(GraphDatabaseService):
    """
    Azure Cosmos DB Gremlin API implementation.

    Uses Cosmos DB with Gremlin API for graph storage, providing
    compatibility with existing Gremlin queries from Neptune.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        database_name: str = "aura-graph",
        container_name: str = "code-entities",
        key: str | None = None,
    ):
        self.endpoint = endpoint or os.environ.get("COSMOS_ENDPOINT")
        self.database_name = database_name
        self.container_name = container_name
        self.key = key or os.environ.get("COSMOS_KEY")

        self._client: "CosmosClient | None" = None
        self._database: "DatabaseProxy | None" = None
        self._container: "ContainerProxy | None" = None
        self._connected = False

        # In-memory mock storage when SDK not available
        self._mock_entities: dict[str, dict[str, Any]] = {}
        self._mock_relationships: dict[str, dict[str, Any]] = {}

    @property
    def is_mock_mode(self) -> bool:
        """Check if running in mock mode."""
        return not COSMOS_AVAILABLE or not self.endpoint

    async def connect(self) -> bool:
        """Connect to Cosmos DB."""
        if self.is_mock_mode:
            logger.info("Cosmos DB running in mock mode")
            self._connected = True
            return True

        try:
            if self.key:
                self._client = CosmosClient(str(self.endpoint), credential=self.key)
            else:
                credential = DefaultAzureCredential()
                self._client = CosmosClient(str(self.endpoint), credential=credential)

            self._database = self._client.get_database_client(self.database_name)
            self._container = self._database.get_container_client(self.container_name)

            self._connected = True
            logger.info(
                f"Connected to Cosmos DB: {self.database_name}/{self.container_name}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Cosmos DB: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Cosmos DB."""
        self._connected = False
        self._client = None
        self._database = None
        self._container = None

    async def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    async def add_entity(self, entity: GraphEntity) -> str:
        """Add a code entity to the graph."""
        if self.is_mock_mode:
            self._mock_entities[entity.id] = entity.to_dict()
            return entity.id

        if self._container is None:
            raise RuntimeError("Not connected to Cosmos DB")

        doc = {
            "id": entity.id,
            "partitionKey": entity.repository,
            "entity_type": entity.entity_type.value,
            "name": entity.name,
            "repository": entity.repository,
            "file_path": entity.file_path,
            "properties": entity.properties,
            "doc_type": "vertex",
        }
        self._container.upsert_item(doc)
        return entity.id

    async def get_entity(self, entity_id: str) -> GraphEntity | None:
        """Get entity by ID."""
        if self.is_mock_mode:
            data = self._mock_entities.get(entity_id)
            if data:
                return GraphEntity.from_dict(data)
            return None

        if self._container is None:
            raise RuntimeError("Not connected to Cosmos DB")

        try:
            # Query across partitions
            query = "SELECT * FROM c WHERE c.id = @id AND c.doc_type = 'vertex'"
            items = list(
                self._container.query_items(
                    query=query,
                    parameters=[{"name": "@id", "value": entity_id}],
                    enable_cross_partition_query=True,
                )
            )
            if items:
                item = items[0]
                return GraphEntity(
                    id=item["id"],
                    entity_type=EntityType(item.get("entity_type", "file")),
                    name=item.get("name", ""),
                    repository=item.get("repository", ""),
                    file_path=item.get("file_path", ""),
                    properties=item.get("properties", {}),
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get entity {entity_id}: {e}")
            return None

    async def update_entity(self, entity: GraphEntity) -> bool:
        """Update an existing entity."""
        if self.is_mock_mode:
            if entity.id in self._mock_entities:
                self._mock_entities[entity.id] = entity.to_dict()
                return True
            return False

        try:
            await self.add_entity(entity)  # upsert
            return True
        except Exception as e:
            logger.error(f"Failed to update entity {entity.id}: {e}")
            return False

    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity."""
        if self.is_mock_mode:
            if entity_id in self._mock_entities:
                del self._mock_entities[entity_id]
                # Also delete related relationships
                to_delete = [
                    k
                    for k, v in self._mock_relationships.items()
                    if v.get("source_id") == entity_id
                    or v.get("target_id") == entity_id
                ]
                for k in to_delete:
                    del self._mock_relationships[k]
                return True
            return False

        if self._container is None:
            raise RuntimeError("Not connected to Cosmos DB")

        try:
            entity = await self.get_entity(entity_id)
            if entity:
                self._container.delete_item(entity_id, partition_key=entity.repository)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete entity {entity_id}: {e}")
            return False

    async def add_relationship(self, relationship: GraphRelationship) -> str:
        """Add a relationship between entities."""
        if self.is_mock_mode:
            self._mock_relationships[relationship.id] = relationship.to_dict()
            return relationship.id

        if self._container is None:
            raise RuntimeError("Not connected to Cosmos DB")

        doc = {
            "id": relationship.id,
            "partitionKey": relationship.source_id,
            "relationship_type": relationship.relationship_type.value,
            "source_id": relationship.source_id,
            "target_id": relationship.target_id,
            "properties": relationship.properties,
            "weight": relationship.weight,
            "doc_type": "edge",
        }
        self._container.upsert_item(doc)
        return relationship.id

    async def get_relationships(
        self,
        entity_id: str,
        relationship_type: RelationshipType | None = None,
        direction: str = "both",
    ) -> list[GraphRelationship]:
        """Get relationships for an entity."""
        if self.is_mock_mode:
            results = []
            for r in self._mock_relationships.values():
                if direction in ("out", "both") and r.get("source_id") == entity_id:
                    if (
                        not relationship_type
                        or r.get("relationship_type") == relationship_type.value
                    ):
                        results.append(GraphRelationship.from_dict(r))
                if direction in ("in", "both") and r.get("target_id") == entity_id:
                    if (
                        not relationship_type
                        or r.get("relationship_type") == relationship_type.value
                    ):
                        results.append(GraphRelationship.from_dict(r))
            return results

        if self._container is None:
            raise RuntimeError("Not connected to Cosmos DB")

        query = "SELECT * FROM c WHERE c.doc_type = 'edge' AND "
        params = []

        if direction == "out":
            query += "c.source_id = @entityId"
        elif direction == "in":
            query += "c.target_id = @entityId"
        else:
            query += "(c.source_id = @entityId OR c.target_id = @entityId)"

        params.append({"name": "@entityId", "value": entity_id})

        if relationship_type:
            query += " AND c.relationship_type = @relType"
            params.append({"name": "@relType", "value": relationship_type.value})

        items = list(
            self._container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )

        return [
            GraphRelationship(
                id=item["id"],
                relationship_type=RelationshipType(
                    item.get("relationship_type", "references")
                ),
                source_id=item.get("source_id", ""),
                target_id=item.get("target_id", ""),
                properties=item.get("properties", {}),
                weight=item.get("weight", 1.0),
            )
            for item in items
        ]

    async def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship."""
        if self.is_mock_mode:
            if relationship_id in self._mock_relationships:
                del self._mock_relationships[relationship_id]
                return True
            return False

        if self._container is None:
            raise RuntimeError("Not connected to Cosmos DB")

        try:
            # Find the relationship to get partition key
            query = "SELECT * FROM c WHERE c.id = @id AND c.doc_type = 'edge'"
            items = list(
                self._container.query_items(
                    query=query,
                    parameters=[{"name": "@id", "value": relationship_id}],
                    enable_cross_partition_query=True,
                )
            )
            if items:
                self._container.delete_item(
                    relationship_id, partition_key=str(items[0]["partitionKey"])
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete relationship {relationship_id}: {e}")
            return False

    async def find_related_code(
        self,
        entity_id: str,
        max_depth: int = 2,
        relationship_types: list[RelationshipType] | None = None,
    ) -> GraphQueryResult:
        """Find related code via traversal."""
        visited_entities: set[str] = set()
        visited_relationships: set[str] = set()
        entities: list[GraphEntity] = []
        relationships: list[GraphRelationship] = []

        async def traverse(current_id: str, depth: int):
            if depth > max_depth or current_id in visited_entities:
                return
            visited_entities.add(current_id)

            entity = await self.get_entity(current_id)
            if entity:
                entities.append(entity)

            for rel_type in relationship_types or list(RelationshipType):
                rels = await self.get_relationships(current_id, rel_type, "out")
                for rel in rels:
                    if rel.id not in visited_relationships:
                        visited_relationships.add(rel.id)
                        relationships.append(rel)
                        await traverse(rel.target_id, depth + 1)

        await traverse(entity_id, 0)
        return GraphQueryResult(entities=entities, relationships=relationships)

    async def search_by_name(
        self,
        name_pattern: str,
        entity_types: list[EntityType] | None = None,
        repository: str | None = None,
        limit: int = 100,
    ) -> list[GraphEntity]:
        """Search entities by name."""
        if self.is_mock_mode:
            results = []
            pattern = name_pattern.lower().replace("*", "")
            for e in self._mock_entities.values():
                if pattern in e.get("name", "").lower():
                    if (
                        entity_types
                        and EntityType(e.get("entity_type")) not in entity_types
                    ):
                        continue
                    if repository and e.get("repository") != repository:
                        continue
                    results.append(GraphEntity.from_dict(e))
                    if len(results) >= limit:
                        break
            return results

        if self._container is None:
            raise RuntimeError("Not connected to Cosmos DB")

        query = "SELECT * FROM c WHERE c.doc_type = 'vertex' AND CONTAINS(LOWER(c.name), @pattern)"
        params: list[dict[str, Any]] = [
            {"name": "@pattern", "value": name_pattern.lower().replace("*", "")}
        ]

        if entity_types:
            types = [et.value for et in entity_types]
            query += " AND ARRAY_CONTAINS(@types, c.entity_type)"
            params.append({"name": "@types", "value": types})

        if repository:
            query += " AND c.repository = @repo"
            params.append({"name": "@repo", "value": repository})

        query += f" OFFSET 0 LIMIT {limit}"

        items = list(
            self._container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )

        return [
            GraphEntity(
                id=item["id"],
                entity_type=EntityType(item.get("entity_type", "file")),
                name=item.get("name", ""),
                repository=item.get("repository", ""),
                file_path=item.get("file_path", ""),
                properties=item.get("properties", {}),
            )
            for item in items
        ]

    async def delete_by_repository(self, repository: str) -> int:
        """Delete all entities for a repository."""
        if self.is_mock_mode:
            to_delete = [
                k
                for k, v in self._mock_entities.items()
                if v.get("repository") == repository
            ]
            for k in to_delete:
                del self._mock_entities[k]
            # Delete relationships
            to_delete_rels = list(self._mock_relationships.keys())
            for k in to_delete_rels:
                del self._mock_relationships[k]
            return len(to_delete)

        if self._container is None:
            raise RuntimeError("Not connected to Cosmos DB")

        query = "SELECT c.id FROM c WHERE c.repository = @repo"
        items = list(
            self._container.query_items(
                query=query,
                parameters=[{"name": "@repo", "value": repository}],
                enable_cross_partition_query=True,
            )
        )

        count = 0
        for item in items:
            try:
                self._container.delete_item(str(item["id"]), partition_key=repository)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to delete item {item['id']}: {e}")

        return count

    async def delete_by_file_path(self, file_path: str, repository: str) -> int:
        """Delete entities for a file."""
        if self.is_mock_mode:
            to_delete = [
                k
                for k, v in self._mock_entities.items()
                if v.get("file_path") == file_path and v.get("repository") == repository
            ]
            for k in to_delete:
                del self._mock_entities[k]
            return len(to_delete)

        if self._container is None:
            raise RuntimeError("Not connected to Cosmos DB")

        query = "SELECT c.id FROM c WHERE c.file_path = @path AND c.repository = @repo"
        items = list(
            self._container.query_items(
                query=query,
                parameters=[
                    {"name": "@path", "value": file_path},
                    {"name": "@repo", "value": repository},
                ],
                enable_cross_partition_query=True,
            )
        )

        count = 0
        for item in items:
            try:
                self._container.delete_item(str(item["id"]), partition_key=repository)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to delete item {item['id']}: {e}")

        return count

    async def get_health(self) -> dict[str, Any]:
        """Get health status."""
        return {
            "status": "healthy" if self._connected else "disconnected",
            "mode": "mock" if self.is_mock_mode else "azure",
            "endpoint": self.endpoint,
            "database": self.database_name,
            "container": self.container_name,
        }

    async def get_statistics(self) -> dict[str, Any]:
        """Get graph statistics."""
        if self.is_mock_mode:
            return {
                "entity_count": len(self._mock_entities),
                "relationship_count": len(self._mock_relationships),
            }

        if self._container is None:
            raise RuntimeError("Not connected to Cosmos DB")

        try:
            vertex_count = list(
                self._container.query_items(
                    query="SELECT VALUE COUNT(1) FROM c WHERE c.doc_type = 'vertex'",
                    enable_cross_partition_query=True,
                )
            )[0]

            edge_count = list(
                self._container.query_items(
                    query="SELECT VALUE COUNT(1) FROM c WHERE c.doc_type = 'edge'",
                    enable_cross_partition_query=True,
                )
            )[0]

            return {
                "entity_count": vertex_count,
                "relationship_count": edge_count,
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {"entity_count": "unknown", "relationship_count": "unknown"}
