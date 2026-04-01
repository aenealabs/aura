"""
Project Aura - Neptune Graph Adapter

Adapter that wraps NeptuneGraphService to implement GraphDatabaseService interface.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
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
from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

logger = logging.getLogger(__name__)


class NeptuneGraphAdapter(GraphDatabaseService):
    """
    Adapter for AWS Neptune that implements GraphDatabaseService interface.

    Wraps the existing NeptuneGraphService to provide a cloud-agnostic API.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        region: str = "us-east-1",
    ):
        self.endpoint = endpoint
        self.region = region
        self._service: NeptuneGraphService | None = None
        self._connected = False

    def _get_service(self) -> NeptuneGraphService:
        """Get or create the underlying Neptune service."""
        if self._service is None:
            mode = NeptuneMode.AWS if self.endpoint else NeptuneMode.MOCK
            self._service = NeptuneGraphService(
                mode=mode,
                endpoint=self.endpoint,
            )
        return self._service

    async def connect(self) -> bool:
        """Establish connection to Neptune."""
        try:
            service = self._get_service()
            # Neptune connections are established on first query
            self._connected = True
            logger.info(f"Neptune adapter connected (mode: {service.mode.value})")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neptune: {e}")
            return False

    async def disconnect(self) -> None:
        """Close Neptune connection."""
        self._connected = False
        self._service = None

    async def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    async def add_entity(self, entity: GraphEntity) -> str:
        """Add a code entity to the graph."""
        service = self._get_service()
        # NeptuneGraphService.add_code_entity has different signature
        # Parameters: name, entity_type, file_path, line_number, parent, metadata
        line_number = 0
        if entity.properties and "line_number" in entity.properties:
            line_num_value = entity.properties["line_number"]
            line_number = (
                int(line_num_value) if isinstance(line_num_value, (int, str)) else 0
            )

        # Build metadata dict from entity properties
        metadata: dict[str, Any] = dict(entity.properties) if entity.properties else {}
        metadata["repository"] = entity.repository

        entity_id = service.add_code_entity(
            name=entity.name,
            entity_type=entity.entity_type.value,
            file_path=entity.file_path,
            line_number=line_number,
            parent=None,
            metadata=metadata,
        )
        return entity_id

    async def get_entity(self, entity_id: str) -> GraphEntity | None:
        """Get an entity by ID."""
        service = self._get_service()
        # Use search to find by ID
        results = service.search_by_name(entity_id, limit=1)
        if results:
            r = results[0]
            return GraphEntity(
                id=r.get("id", entity_id),
                entity_type=EntityType(r.get("entity_type", "file")),
                name=r.get("name", ""),
                repository=r.get("repository", ""),
                file_path=r.get("file_path", ""),
                properties=r.get("properties", {}),
            )
        return None

    async def update_entity(self, entity: GraphEntity) -> bool:
        """Update an existing entity."""
        # Neptune Gremlin: delete and re-add
        await self.delete_entity(entity.id)
        await self.add_entity(entity)
        return True

    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity."""
        service = self._get_service()
        return service.delete_entity(entity_id)

    async def add_relationship(self, relationship: GraphRelationship) -> str:
        """Add a relationship between entities."""
        service = self._get_service()
        # NeptuneGraphService.add_relationship has different signature
        # Parameters: from_entity, to_entity, relationship, metadata
        # Returns bool, not str
        _success = service.add_relationship(  # noqa: F841
            from_entity=relationship.source_id,
            to_entity=relationship.target_id,
            relationship=relationship.relationship_type.value,
            metadata=relationship.properties,
        )
        # Generate a relationship ID since the service doesn't return one
        edge_id = f"{relationship.source_id}_{relationship.relationship_type.value}_{relationship.target_id}"
        return edge_id

    async def get_relationships(
        self,
        entity_id: str,
        relationship_type: RelationshipType | None = None,
        direction: str = "both",
    ) -> list[GraphRelationship]:
        """Get relationships for an entity."""
        service = self._get_service()
        # NeptuneGraphService.find_related_code has different signature
        # Parameters: entity_name, max_depth, relationship_types
        # Returns list[dict[str, Any]], not a dict with "relationships" key
        results_list = service.find_related_code(
            entity_name=entity_id,
            max_depth=1,
            relationship_types=[relationship_type.value] if relationship_type else None,
        )
        relationships: list[GraphRelationship] = []
        for r in results_list:
            # Each result is a dict representing a related entity with relationship info
            rel_type_str = str(r.get("relationship", "references"))
            relationships.append(
                GraphRelationship(
                    id=str(r.get("id", "")),
                    relationship_type=RelationshipType(rel_type_str),
                    source_id=entity_id,
                    target_id=str(r.get("id", "")),
                    properties=dict(r) if isinstance(r, dict) else {},
                )
            )
        return relationships

    async def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship."""
        service = self._get_service()
        return service.delete_entity(relationship_id)

    async def find_related_code(
        self,
        entity_id: str,
        max_depth: int = 2,
        relationship_types: list[RelationshipType] | None = None,
    ) -> GraphQueryResult:
        """Find related code via graph traversal."""
        service = self._get_service()
        types = [rt.value for rt in relationship_types] if relationship_types else None
        # NeptuneGraphService.find_related_code returns list[dict[str, Any]]
        results_list = service.find_related_code(
            entity_name=entity_id,
            max_depth=max_depth,
            relationship_types=types,
        )

        entities: list[GraphEntity] = []
        relationships: list[GraphRelationship] = []

        # Each result is a related entity with relationship info
        for e in results_list:
            # Convert dict values to strings explicitly
            entity_id_str = str(e.get("id", ""))
            entity_type_str = str(e.get("entity_type", "file"))
            name_str = str(e.get("name", ""))
            repository_str = str(e.get("repository", ""))
            file_path_str = str(e.get("file_path", ""))
            properties_dict: dict[str, Any] = (
                dict(e.get("properties", {}))
                if isinstance(e.get("properties"), dict)
                else {}
            )

            entities.append(
                GraphEntity(
                    id=entity_id_str,
                    entity_type=EntityType(entity_type_str),
                    name=name_str,
                    repository=repository_str,
                    file_path=file_path_str,
                    properties=properties_dict,
                )
            )

            # Build relationships from the traversal info
            if "relationship" in e:
                rel_type_str = str(e.get("relationship", "references"))
                relationships.append(
                    GraphRelationship(
                        id=f"{entity_id}_{rel_type_str}_{entity_id_str}",
                        relationship_type=RelationshipType(rel_type_str),
                        source_id=entity_id,
                        target_id=entity_id_str,
                        properties={},
                    )
                )

        return GraphQueryResult(entities=entities, relationships=relationships)

    async def search_by_name(
        self,
        name_pattern: str,
        entity_types: list[EntityType] | None = None,
        repository: str | None = None,
        limit: int = 100,
    ) -> list[GraphEntity]:
        """Search entities by name."""
        service = self._get_service()
        # NeptuneGraphService.search_by_name only accepts name_pattern and limit
        results = service.search_by_name(
            name_pattern=name_pattern,
            limit=limit,
        )

        # Pre-compute filter sets for O(1) lookups instead of O(n) list scan
        allowed_types = {et.value for et in entity_types} if entity_types else None

        entities: list[GraphEntity] = []
        for e in results:
            # Filter by entity_types and repository if specified
            entity_type_str = str(e.get("entity_type", "file"))
            repository_str = str(e.get("repository", ""))

            # Apply filters
            if allowed_types and entity_type_str not in allowed_types:
                continue
            if repository and repository_str != repository:
                continue

            # Convert dict values to strings explicitly
            entity_id_str = str(e.get("id", ""))
            name_str = str(e.get("name", ""))
            file_path_str = str(e.get("file_path", ""))
            properties_dict: dict[str, Any] = (
                dict(e.get("properties", {}))
                if isinstance(e.get("properties"), dict)
                else {}
            )

            entities.append(
                GraphEntity(
                    id=entity_id_str,
                    entity_type=EntityType(entity_type_str),
                    name=name_str,
                    repository=repository_str,
                    file_path=file_path_str,
                    properties=properties_dict,
                )
            )
        return entities

    async def delete_by_repository(self, repository: str) -> int:
        """Delete all entities for a repository."""
        service = self._get_service()
        return service.delete_by_repository(repository)

    async def delete_by_file_path(self, file_path: str, repository: str) -> int:
        """Delete entities for a file."""
        service = self._get_service()
        # NeptuneGraphService.delete_entities_by_file only takes file_path
        return service.delete_entities_by_file(file_path)

    async def get_health(self) -> dict[str, Any]:
        """Get Neptune health status."""
        service = self._get_service()
        return {
            "status": "healthy" if self._connected else "disconnected",
            "mode": service.mode.value,
            "endpoint": self.endpoint,
            "region": self.region,
        }

    async def get_statistics(self) -> dict[str, Any]:
        """Get graph statistics."""
        service = self._get_service()
        if hasattr(service, "get_statistics"):
            stats = service.get_statistics()
            # Ensure we return a properly typed dict
            return dict(stats) if isinstance(stats, dict) else {}
        return {
            "entity_count": "unknown",
            "relationship_count": "unknown",
        }
