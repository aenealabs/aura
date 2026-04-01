"""
Project Aura - Graph Database Abstraction

Abstract interface for graph database operations.
Implementations: AWS Neptune (Gremlin), Azure Cosmos DB (Gremlin API)

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EntityType(Enum):
    """Types of code entities that can be stored in the graph."""

    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    MODULE = "module"
    VARIABLE = "variable"
    IMPORT = "import"
    PACKAGE = "package"


class RelationshipType(Enum):
    """Types of relationships between code entities."""

    CONTAINS = "contains"
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    DEPENDS_ON = "depends_on"
    REFERENCES = "references"
    DEFINES = "defines"
    USES = "uses"


@dataclass
class GraphEntity:
    """Represents a vertex/node in the code graph."""

    id: str
    entity_type: EntityType
    name: str
    repository: str
    file_path: str
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary for storage."""
        return {
            "id": self.id,
            "entity_type": self.entity_type.value,
            "name": self.name,
            "repository": self.repository,
            "file_path": self.file_path,
            "properties": self.properties,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphEntity":
        """Create entity from dictionary."""
        return cls(
            id=data["id"],
            entity_type=EntityType(data["entity_type"]),
            name=data["name"],
            repository=data["repository"],
            file_path=data["file_path"],
            properties=data.get("properties", {}),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else None
            ),
        )


@dataclass
class GraphRelationship:
    """Represents an edge in the code graph."""

    id: str
    relationship_type: RelationshipType
    source_id: str
    target_id: str
    properties: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert relationship to dictionary for storage."""
        return {
            "id": self.id,
            "relationship_type": self.relationship_type.value,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "properties": self.properties,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphRelationship":
        """Create relationship from dictionary."""
        return cls(
            id=data["id"],
            relationship_type=RelationshipType(data["relationship_type"]),
            source_id=data["source_id"],
            target_id=data["target_id"],
            properties=data.get("properties", {}),
            weight=data.get("weight", 1.0),
        )


@dataclass
class GraphQueryResult:
    """Result from a graph query."""

    entities: list[GraphEntity]
    relationships: list[GraphRelationship]
    metadata: dict[str, Any] = field(default_factory=dict)


class GraphDatabaseService(ABC):
    """
    Abstract interface for graph database operations.

    Implementations:
    - AWS: NeptuneGraphService (Gremlin)
    - Azure: CosmosDBGraphService (Gremlin API)
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the graph database."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the database connection."""

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if the database connection is active."""

    # Entity Operations
    @abstractmethod
    async def add_entity(self, entity: GraphEntity) -> str:
        """
        Add a code entity (vertex) to the graph.

        Args:
            entity: The entity to add

        Returns:
            The ID of the created entity
        """

    @abstractmethod
    async def get_entity(self, entity_id: str) -> GraphEntity | None:
        """
        Get an entity by its ID.

        Args:
            entity_id: The entity ID

        Returns:
            The entity if found, None otherwise
        """

    @abstractmethod
    async def update_entity(self, entity: GraphEntity) -> bool:
        """
        Update an existing entity.

        Args:
            entity: The entity with updated properties

        Returns:
            True if updated successfully
        """

    @abstractmethod
    async def delete_entity(self, entity_id: str) -> bool:
        """
        Delete an entity and its relationships.

        Args:
            entity_id: The entity ID to delete

        Returns:
            True if deleted successfully
        """

    # Relationship Operations
    @abstractmethod
    async def add_relationship(self, relationship: GraphRelationship) -> str:
        """
        Add a relationship (edge) between two entities.

        Args:
            relationship: The relationship to add

        Returns:
            The ID of the created relationship
        """

    @abstractmethod
    async def get_relationships(
        self,
        entity_id: str,
        relationship_type: RelationshipType | None = None,
        direction: str = "both",  # "in", "out", "both"
    ) -> list[GraphRelationship]:
        """
        Get relationships for an entity.

        Args:
            entity_id: The entity ID
            relationship_type: Optional filter by relationship type
            direction: Direction of relationships to retrieve

        Returns:
            List of matching relationships
        """

    @abstractmethod
    async def delete_relationship(self, relationship_id: str) -> bool:
        """
        Delete a relationship.

        Args:
            relationship_id: The relationship ID to delete

        Returns:
            True if deleted successfully
        """

    # Query Operations
    @abstractmethod
    async def find_related_code(
        self,
        entity_id: str,
        max_depth: int = 2,
        relationship_types: list[RelationshipType] | None = None,
    ) -> GraphQueryResult:
        """
        Find code entities related to a given entity via graph traversal.

        Args:
            entity_id: Starting entity ID
            max_depth: Maximum traversal depth
            relationship_types: Optional filter by relationship types

        Returns:
            Query result with entities and relationships
        """

    @abstractmethod
    async def search_by_name(
        self,
        name_pattern: str,
        entity_types: list[EntityType] | None = None,
        repository: str | None = None,
        limit: int = 100,
    ) -> list[GraphEntity]:
        """
        Search for entities by name pattern.

        Args:
            name_pattern: Name pattern to search for (supports wildcards)
            entity_types: Optional filter by entity types
            repository: Optional filter by repository
            limit: Maximum number of results

        Returns:
            List of matching entities
        """

    # Bulk Operations
    @abstractmethod
    async def delete_by_repository(self, repository: str) -> int:
        """
        Delete all entities and relationships for a repository.

        Args:
            repository: The repository identifier

        Returns:
            Number of entities deleted
        """

    @abstractmethod
    async def delete_by_file_path(self, file_path: str, repository: str) -> int:
        """
        Delete all entities for a specific file.

        Args:
            file_path: The file path
            repository: The repository identifier

        Returns:
            Number of entities deleted
        """

    # Health and Metrics
    @abstractmethod
    async def get_health(self) -> dict[str, Any]:
        """
        Get database health status.

        Returns:
            Health status including connection state, latency, etc.
        """

    @abstractmethod
    async def get_statistics(self) -> dict[str, Any]:
        """
        Get graph statistics.

        Returns:
            Statistics including entity count, relationship count, etc.
        """
