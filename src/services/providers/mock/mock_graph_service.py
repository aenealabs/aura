"""
Project Aura - Mock Graph Service

In-memory mock implementation of GraphDatabaseService for testing.
"""

import logging
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


class MockGraphService(GraphDatabaseService):
    """Mock graph database for testing."""

    def __init__(self) -> None:
        self._entities: dict[str, GraphEntity] = {}
        self._relationships: dict[str, GraphRelationship] = {}
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        logger.info("MockGraphService connected")
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def add_entity(self, entity: GraphEntity) -> str:
        self._entities[entity.id] = entity
        return entity.id

    async def get_entity(self, entity_id: str) -> GraphEntity | None:
        return self._entities.get(entity_id)

    async def update_entity(self, entity: GraphEntity) -> bool:
        if entity.id in self._entities:
            self._entities[entity.id] = entity
            return True
        return False

    async def delete_entity(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            # Delete related relationships
            to_delete = [
                k
                for k, v in self._relationships.items()
                if v.source_id == entity_id or v.target_id == entity_id
            ]
            for k in to_delete:
                del self._relationships[k]
            return True
        return False

    async def add_relationship(self, relationship: GraphRelationship) -> str:
        self._relationships[relationship.id] = relationship
        return relationship.id

    async def get_relationships(
        self,
        entity_id: str,
        relationship_type: RelationshipType | None = None,
        direction: str = "both",
    ) -> list[GraphRelationship]:
        results = []
        for rel in self._relationships.values():
            # Compare enum values (strings) rather than enum instances to handle
            # forked process class identity issues. In forked subprocesses, enum
            # classes may be reimported, creating different class objects where
            # RelationshipType.CONTAINS != RelationshipType.CONTAINS due to
            # Python enum identity comparison semantics.
            matches_type = (
                relationship_type is None
                or rel.relationship_type.value == relationship_type.value
            )
            if (
                direction in ("out", "both")
                and rel.source_id == entity_id
                and matches_type
            ):
                results.append(rel)
            if (
                direction in ("in", "both")
                and rel.target_id == entity_id
                and matches_type
            ):
                results.append(rel)
        return results

    async def delete_relationship(self, relationship_id: str) -> bool:
        if relationship_id in self._relationships:
            del self._relationships[relationship_id]
            return True
        return False

    async def find_related_code(
        self,
        entity_id: str,
        max_depth: int = 2,
        relationship_types: list[RelationshipType] | None = None,
    ) -> GraphQueryResult:
        visited = set()
        entities = []
        relationships = []
        relationship_ids: set[str] = set()  # O(1) lookup instead of O(n) list scan

        async def traverse(current_id: str, depth: int):
            if depth > max_depth or current_id in visited:
                return
            visited.add(current_id)

            entity = await self.get_entity(current_id)
            if entity:
                entities.append(entity)

            for rel_type in relationship_types or list(RelationshipType):
                rels = await self.get_relationships(current_id, rel_type, "out")
                for rel in rels:
                    if rel.id not in relationship_ids:  # O(1) set lookup
                        relationship_ids.add(rel.id)
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
        pattern = name_pattern.lower().replace("*", "")
        results = []
        for entity in self._entities.values():
            if pattern in entity.name.lower():
                if entity_types and entity.entity_type not in entity_types:
                    continue
                if repository and entity.repository != repository:
                    continue
                results.append(entity)
                if len(results) >= limit:
                    break
        return results

    async def delete_by_repository(self, repository: str) -> int:
        to_delete = [k for k, v in self._entities.items() if v.repository == repository]
        for k in to_delete:
            del self._entities[k]
        return len(to_delete)

    async def delete_by_file_path(self, file_path: str, repository: str) -> int:
        to_delete = [
            k
            for k, v in self._entities.items()
            if v.file_path == file_path and v.repository == repository
        ]
        for k in to_delete:
            del self._entities[k]
        return len(to_delete)

    async def get_health(self) -> dict[str, Any]:
        return {"status": "healthy", "mode": "mock"}

    async def get_statistics(self) -> dict[str, Any]:
        return {
            "entity_count": len(self._entities),
            "relationship_count": len(self._relationships),
        }
