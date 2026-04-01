"""
Service Adapters for Project Aura

Provides adapter classes that wrap real AWS services (Neptune, OpenSearch) with the
same interface as the mock implementations used in agent_orchestrator.py.

This allows seamless switching between mock and real services based on environment.

Usage:
    from src.services.service_adapters import create_graph_agent, create_vector_store

    # Returns mock in dev, real adapter in production
    graph_agent = create_graph_agent()
    vector_store = create_vector_store()
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.client import BedrockRuntimeClient

    from src.services.neptune_graph_service import NeptuneGraphService
    from src.services.opensearch_vector_service import OpenSearchVectorService

logger = logging.getLogger(__name__)


class GraphAgentProtocol(Protocol):
    """Protocol defining the GraphBuilderAgent interface."""

    def parse_source_code(
        self, _code_content: str, filename: str | Path
    ) -> dict[str, Any]: ...

    def add_node(self, node_id: str, label: str, **properties: Any) -> None: ...

    def add_edge(
        self, source_id: str, target_id: str, type: str, **properties: Any
    ) -> None: ...

    def run_gremlin_query(self, source_entity: str) -> list[str]: ...


class VectorStoreProtocol(Protocol):
    """Protocol defining the OpenSearchVectorStore interface."""

    def run_knn_search(self, query: str) -> list[str]: ...


class NeptuneGraphAdapter:
    """
    Adapter that wraps NeptuneGraphService with GraphBuilderAgent interface.

    This adapter translates calls from the orchestrator's expected GraphBuilderAgent
    interface to the real NeptuneGraphService methods.
    """

    def __init__(self, neptune_service: "NeptuneGraphService") -> None:
        """
        Initialize adapter with real Neptune service.

        Args:
            neptune_service: Configured NeptuneGraphService instance
        """
        from src.services.neptune_graph_service import NeptuneGraphService

        self.neptune: NeptuneGraphService = neptune_service
        self.ckge_graph: dict[str, dict[str, Any]] = {}  # Local cache for compatibility
        logger.info("NeptuneGraphAdapter initialized")

    def parse_source_code(
        self, _code_content: str, filename: str | Path
    ) -> dict[str, Any]:
        """
        Parse source code and store entities in Neptune.

        This method delegates to AST parser for actual parsing, then stores
        the results in Neptune via add_code_entity calls.

        Args:
            _code_content: Source code content
            filename: Name of file being parsed

        Returns:
            Parsed data structure with classes, methods, and dependencies
        """
        from src.agents.ast_parser_agent import ASTParserAgent

        filename_str = str(filename)
        logger.info(f"Parsing code structure for {filename_str}...")

        # Use the real AST parser
        parser = ASTParserAgent()
        file_path = Path(filename_str)

        # Create temp file if parsing in-memory content
        if not file_path.exists() and _code_content:
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(_code_content)
                temp_path = Path(f.name)
            try:
                entities = parser.parse_file(temp_path)
            finally:
                temp_path.unlink()
        else:
            entities = parser.parse_file(file_path) if file_path.exists() else []

        # Convert to expected format and store in Neptune
        parsed_data: dict[str, Any] = {
            "file": filename_str,
            "classes": [],
            "dependencies": [],
        }

        for entity in entities:
            # Store entity in Neptune
            entity_id = self.neptune.add_code_entity(
                name=entity.name,
                entity_type=entity.entity_type,
                file_path=filename_str,
                line_number=entity.line_number,
            )

            # Update local cache for backward compatibility
            self.ckge_graph[entity_id] = {
                "label": entity.entity_type.upper(),
                "properties": {
                    "name": entity.name,
                    "file": filename_str,
                    "line": entity.line_number,
                },
                "edges": {},
            }

            # Build parsed_data structure
            if entity.entity_type == "class":
                parsed_data["classes"].append({"name": entity.name, "methods": []})
            elif entity.entity_type == "function":
                # If we have classes, add as method to last class
                if parsed_data["classes"]:
                    parsed_data["classes"][-1]["methods"].append(entity.name)

        logger.info(
            f"Graph built successfully with {len(self.ckge_graph)} entities in Neptune."
        )
        return parsed_data

    def add_node(self, node_id: str, label: str, **properties: Any) -> None:
        """
        Add a node to the graph.

        Args:
            node_id: Unique identifier for the node
            label: Node type label (CLASS, METHOD, FILE, etc.)
            **properties: Additional properties
        """
        # Extract file path and line number from properties or use defaults
        file_path = properties.get("file", "unknown")
        line_number = properties.get("line", 1)
        name = properties.get("name", node_id)

        # Map label to entity_type
        entity_type = label.lower()

        # Store in Neptune
        self.neptune.add_code_entity(
            name=name,
            entity_type=entity_type,
            file_path=str(file_path),
            line_number=line_number,
            metadata=properties,
        )

        # Update local cache
        self.ckge_graph[node_id] = {
            "label": label,
            "properties": properties,
            "edges": {},
        }

    def add_edge(
        self, source_id: str, target_id: str, type: str, **properties: Any
    ) -> None:
        """
        Add an edge (relationship) between two nodes.

        Args:
            source_id: Source node ID
            target_id: Target node ID
            type: Relationship type (CONTAINS, CALLS, IMPORTS, etc.)
            **properties: Additional edge properties
        """
        # Store in Neptune
        self.neptune.add_relationship(
            from_entity=source_id,
            to_entity=target_id,
            relationship=type,
            metadata=properties if properties else None,
        )

        # Update local cache
        if source_id in self.ckge_graph:
            self.ckge_graph[source_id]["edges"].setdefault(type, []).append(target_id)

    def run_gremlin_query(self, source_entity: str) -> list[str]:
        """
        Query the graph for structural context around an entity.

        Args:
            source_entity: Entity name to query

        Returns:
            List of context strings describing relationships
        """
        # Query Neptune for related entities
        related = self.neptune.find_related_code(source_entity, max_depth=2)

        if not related:
            # Fallback: try searching by name pattern
            related = self.neptune.search_by_name(source_entity, limit=5)

        if related:
            # Format as context strings
            dependencies = []
            for entity in related:
                rel = entity.get("relationship", "RELATED_TO")
                name = entity.get("name", entity.get("id", "unknown"))
                dependencies.append(f"{name} via {rel}")

            if dependencies:
                return [
                    f"Structural Context (Graph): {source_entity} integrates with: {', '.join(dependencies)}"
                ]

        return [
            f"Structural Context (Graph): No direct dependencies found for {source_entity}."
        ]


class OpenSearchVectorAdapter:
    """
    Adapter that wraps OpenSearchVectorService with OpenSearchVectorStore interface.

    This adapter translates calls from the orchestrator's expected OpenSearchVectorStore
    interface to the real OpenSearchVectorService methods.
    """

    def __init__(self, opensearch_service: "OpenSearchVectorService") -> None:
        """
        Initialize adapter with real OpenSearch service.

        Args:
            opensearch_service: Configured OpenSearchVectorService instance
        """
        from src.services.opensearch_vector_service import OpenSearchVectorService

        self.opensearch: OpenSearchVectorService = opensearch_service
        self._embedding_client: BedrockRuntimeClient | None = (
            None  # Lazy-loaded embedding client
        )
        logger.info("OpenSearchVectorAdapter initialized")

    def _get_embedding(self, text: str) -> list[float]:
        """
        Generate embedding vector for text using Bedrock.

        Falls back to mock vector if Bedrock unavailable.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            # Try to use Bedrock Titan embeddings
            import json

            import boto3

            if self._embedding_client is None:
                self._embedding_client = boto3.client(
                    "bedrock-runtime", region_name="us-east-1"
                )

            response = self._embedding_client.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                body=json.dumps({"inputText": text}),
            )
            result = json.loads(response["body"].read())
            return cast(list[float], result["embedding"])

        except Exception as e:
            logger.warning(f"Bedrock embedding failed, using mock: {e}")
            # Return mock vector matching expected dimension
            return [0.1] * self.opensearch.vector_dimension

    def run_knn_search(self, query: str) -> list[str]:
        """
        Search for semantically similar content.

        Args:
            query: Search query text

        Returns:
            List of relevant context strings
        """
        # Generate query embedding
        query_vector = self._get_embedding(query)

        # Search OpenSearch
        results = self.opensearch.search_similar(
            query_vector=query_vector, k=5, min_score=0.5
        )

        if not results:
            # Fallback: try metadata search
            if "checksum" in query.lower() or "hash" in query.lower():
                results = self.opensearch.search_by_metadata(
                    filters={"category": "cryptography"}, limit=3
                )

        # Convert to expected string format
        context_strings = []
        for result in results:
            text = result.get("text", "")
            metadata = result.get("metadata", {})

            # Detect if this is a security policy
            if any(
                kw in text.lower()
                for kw in ["security", "policy", "prohibited", "must"]
            ):
                context_strings.append(f"Security Policy: {text}")
            else:
                source = metadata.get("source", metadata.get("file_path", "unknown"))
                context_strings.append(f"Code Context ({source}): {text}")

        if not context_strings:
            # Return default context if nothing found
            return [
                "DataProcessor class handles data pre-processing and checksum generation."
            ]

        return context_strings


def create_graph_agent(use_real: bool | None = None) -> GraphAgentProtocol:
    """
    Factory function to create graph agent (mock or real Neptune adapter).

    Args:
        use_real: Force real or mock mode. If None, auto-detect from environment.

    Returns:
        GraphBuilderAgent (mock) or NeptuneGraphAdapter (real)
    """
    # Auto-detect mode from environment
    if use_real is None:
        use_real = (
            os.getenv("NEPTUNE_ENDPOINT") is not None
            and os.getenv("USE_MOCK_SERVICES", "").lower() != "true"
        )

    if use_real:
        try:
            from src.services.neptune_graph_service import (
                NeptuneGraphService,
                NeptuneMode,
            )

            # Use service discovery endpoint - never hardcode cluster identifiers
            endpoint = os.getenv("NEPTUNE_ENDPOINT", "neptune.aura.local")
            port = int(os.getenv("NEPTUNE_PORT", "8182"))

            neptune = NeptuneGraphService(
                mode=NeptuneMode.AWS, endpoint=endpoint, port=port
            )

            logger.info(f"Created NeptuneGraphAdapter (endpoint: {endpoint})")
            return NeptuneGraphAdapter(neptune)

        except Exception as e:
            logger.warning(
                f"Failed to create Neptune adapter, falling back to mock: {e}"
            )

    # Return mock implementation
    from src.agents.agent_orchestrator import GraphBuilderAgent

    logger.info("Created mock GraphBuilderAgent")
    return GraphBuilderAgent()


def create_vector_store(use_real: bool | None = None) -> VectorStoreProtocol:
    """
    Factory function to create vector store (mock or real OpenSearch adapter).

    Args:
        use_real: Force real or mock mode. If None, auto-detect from environment.

    Returns:
        OpenSearchVectorStore (mock) or OpenSearchVectorAdapter (real)
    """
    # Auto-detect mode from environment
    if use_real is None:
        use_real = (
            os.getenv("OPENSEARCH_ENDPOINT") is not None
            and os.getenv("USE_MOCK_SERVICES", "").lower() != "true"
        )

    if use_real:
        try:
            from src.services.opensearch_vector_service import (
                OpenSearchMode,
                OpenSearchVectorService,
            )

            # Use service discovery endpoint - never hardcode domain identifiers
            endpoint = os.getenv("OPENSEARCH_ENDPOINT", "opensearch.aura.local")
            port = int(os.getenv("OPENSEARCH_PORT", "443"))
            vector_dim = int(os.getenv("VECTOR_DIMENSION", "1024"))

            opensearch = OpenSearchVectorService(
                mode=OpenSearchMode.AWS,
                endpoint=endpoint,
                port=port,
                vector_dimension=vector_dim,
            )

            logger.info(f"Created OpenSearchVectorAdapter (endpoint: {endpoint})")
            return OpenSearchVectorAdapter(opensearch)

        except Exception as e:
            logger.warning(
                f"Failed to create OpenSearch adapter, falling back to mock: {e}"
            )

    # Return mock implementation
    from src.agents.agent_orchestrator import OpenSearchVectorStore

    logger.info("Created mock OpenSearchVectorStore")
    return OpenSearchVectorStore()
