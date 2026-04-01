"""
Project Aura - Supply Chain Graph Integration

Neptune graph database integration for supply chain security services.
Manages SBOM, Attestation, and License vertices with their relationships.

Vertices:
- SBOM: Software bill of materials document
- Attestation: Signed attestation for an SBOM
- License: SPDX license information
- Dependency: Package dependency (extends existing)

Edges:
- ATTESTED_BY: SBOM → Attestation
- CONTAINS: SBOM → Dependency
- LICENSED_UNDER: Dependency → License
- SUPERSEDES: Attestation → Attestation

Usage:
    from src.services.supply_chain.graph_integration import (
        SupplyChainGraphService,
        get_supply_chain_graph_service,
    )

    service = get_supply_chain_graph_service()
    service.store_sbom(sbom_document)
    service.store_attestation(attestation)
    provenance = service.get_provenance_chain(purl)

Compliance:
- SLSA Level 3: Provenance tracking in immutable graph
- NIST 800-53: AU-10 (Non-repudiation)
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .config import StorageConfig, get_supply_chain_config
from .contracts import (
    Attestation,
    LicenseCategory,
    ProvenanceChain,
    SBOMComponent,
    SBOMDocument,
    VerificationStatus,
)
from .exceptions import GraphIntegrationError

logger = logging.getLogger(__name__)


class GraphMode(Enum):
    """Operating modes for graph service."""

    MOCK = "mock"
    AWS = "aws"


class VertexLabel(Enum):
    """Vertex labels for supply chain graph."""

    SBOM = "SBOM"
    ATTESTATION = "Attestation"
    LICENSE = "License"
    DEPENDENCY = "Dependency"
    REPOSITORY = "Repository"


class EdgeLabel(Enum):
    """Edge labels for supply chain graph."""

    ATTESTED_BY = "ATTESTED_BY"
    CONTAINS = "CONTAINS"
    LICENSED_UNDER = "LICENSED_UNDER"
    SUPERSEDES = "SUPERSEDES"
    GENERATED_FOR = "GENERATED_FOR"
    DEPENDS_ON = "DEPENDS_ON"


@dataclass
class GraphVertex:
    """Representation of a graph vertex."""

    id: str
    label: VertexLabel
    properties: dict[str, Any]


@dataclass
class GraphEdge:
    """Representation of a graph edge."""

    id: str
    label: EdgeLabel
    from_vertex_id: str
    to_vertex_id: str
    properties: dict[str, Any]


def escape_gremlin_string(value: str) -> str:
    """Escape a string for safe use in Gremlin queries."""
    if not isinstance(value, str):
        value = str(value)
    value = value.replace("\\", "\\\\")
    value = value.replace("'", "\\'")
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    value = value.replace("\t", "\\t")
    return value


class SupplyChainGraphService:
    """
    Neptune graph integration for supply chain security.

    Manages the knowledge graph for SBOMs, attestations, and licenses,
    enabling provenance queries and compliance tracking.
    """

    def __init__(
        self,
        config: Optional[StorageConfig] = None,
        mode: GraphMode = GraphMode.MOCK,
    ):
        """Initialize the graph service.

        Args:
            config: Storage configuration
            mode: Operating mode (MOCK or AWS)
        """
        if config is None:
            config = get_supply_chain_config().storage
        self.config = config

        self.mode = mode
        self._client = None

        # Mock storage for testing
        self._mock_vertices: dict[str, GraphVertex] = {}
        self._mock_edges: dict[str, GraphEdge] = {}

        # Initialize connection if AWS mode
        if mode == GraphMode.AWS and config.neptune_endpoint:
            self._init_neptune_client(config.neptune_endpoint)

        logger.info(f"SupplyChainGraphService initialized (mode={mode.value})")

    def _init_neptune_client(self, endpoint: str) -> None:
        """Initialize Neptune Gremlin client."""
        try:
            from gremlin_python.driver import client, serializer

            self._client = client.Client(
                f"wss://{endpoint}:8182/gremlin",
                "g",
                message_serializer=serializer.GraphSONSerializersV2d0(),
            )
            logger.info(f"Connected to Neptune at {endpoint}")
        except ImportError:
            logger.warning("Gremlin Python not available - using mock mode")
            self.mode = GraphMode.MOCK
        except Exception as e:
            logger.error(f"Failed to connect to Neptune: {e}")
            self.mode = GraphMode.MOCK

    # -------------------------------------------------------------------------
    # SBOM Operations
    # -------------------------------------------------------------------------

    def store_sbom(self, sbom: SBOMDocument) -> str:
        """Store an SBOM document in the graph.

        Args:
            sbom: SBOM document to store

        Returns:
            Vertex ID of the stored SBOM
        """
        vertex_id = f"sbom:{sbom.sbom_id}"

        properties = {
            "sbom_id": sbom.sbom_id,
            "name": sbom.name,
            "version": sbom.version,
            "format": sbom.format.value,
            "repository_id": sbom.repository_id,
            "component_count": len(sbom.components),
            "created_at": sbom.created_at.isoformat(),
            "spec_version": sbom.spec_version,
        }

        if sbom.hash_value:
            properties["hash_value"] = sbom.hash_value

        vertex = GraphVertex(
            id=vertex_id,
            label=VertexLabel.SBOM,
            properties=properties,
        )

        self._upsert_vertex(vertex)

        # Store components and relationships
        for component in sbom.components:
            comp_vertex_id = self._store_component(component)
            self._create_edge(
                EdgeLabel.CONTAINS,
                vertex_id,
                comp_vertex_id,
                {"added_at": datetime.now(timezone.utc).isoformat()},
            )

        # Link to repository if exists
        repo_vertex_id = f"repository:{sbom.repository_id}"
        if self._vertex_exists(repo_vertex_id):
            self._create_edge(
                EdgeLabel.GENERATED_FOR,
                vertex_id,
                repo_vertex_id,
                {},
            )

        logger.info(
            f"Stored SBOM {sbom.sbom_id} with {len(sbom.components)} components"
        )
        return vertex_id

    def get_sbom(self, sbom_id: str) -> Optional[dict[str, Any]]:
        """Retrieve SBOM data from the graph.

        Args:
            sbom_id: SBOM identifier

        Returns:
            SBOM properties or None if not found
        """
        vertex_id = f"sbom:{sbom_id}"
        vertex = self._get_vertex(vertex_id)
        return vertex.properties if vertex else None

    def _store_component(self, component: SBOMComponent) -> str:
        """Store an SBOM component as a Dependency vertex.

        Args:
            component: SBOM component to store

        Returns:
            Vertex ID of the stored component
        """
        # Use PURL as vertex ID if available, otherwise generate from name/version
        if component.purl:
            vertex_id = f"dependency:{component.purl}"
        else:
            vertex_id = f"dependency:{component.name}@{component.version}"

        properties = {
            "name": component.name,
            "version": component.version,
            "purl": component.purl or "",
            "type": component.component_type,
            "supplier": component.supplier or "",
            "is_direct": component.is_direct,
        }

        if component.hashes:
            properties["hashes"] = ",".join(
                f"{k}:{v}" for k, v in component.hashes.items()
            )

        vertex = GraphVertex(
            id=vertex_id,
            label=VertexLabel.DEPENDENCY,
            properties=properties,
        )

        self._upsert_vertex(vertex)

        # Store license and create relationship
        if component.licenses:
            for license_id in component.licenses:
                license_vertex_id = self._store_license(license_id)
                self._create_edge(
                    EdgeLabel.LICENSED_UNDER,
                    vertex_id,
                    license_vertex_id,
                    {},
                )

        return vertex_id

    # -------------------------------------------------------------------------
    # Attestation Operations
    # -------------------------------------------------------------------------

    def store_attestation(self, attestation: Attestation) -> str:
        """Store an attestation in the graph.

        Args:
            attestation: Attestation to store

        Returns:
            Vertex ID of the stored attestation
        """
        vertex_id = f"attestation:{attestation.attestation_id}"

        properties = {
            "attestation_id": attestation.attestation_id,
            "sbom_id": attestation.sbom_id,
            "predicate_type": attestation.predicate_type,
            "signing_method": attestation.signing_method.value,
            "signer_identity": attestation.signer_identity or "",
            "created_at": attestation.created_at.isoformat(),
            "signature_truncated": (
                attestation.signature[:64] + "..."
                if len(attestation.signature) > 64
                else attestation.signature
            ),
        }

        if attestation.rekor_log_index:
            properties["rekor_log_index"] = attestation.rekor_log_index

        if attestation.rekor_uuid:
            properties["rekor_uuid"] = attestation.rekor_uuid

        vertex = GraphVertex(
            id=vertex_id,
            label=VertexLabel.ATTESTATION,
            properties=properties,
        )

        self._upsert_vertex(vertex)

        # Link to SBOM
        sbom_vertex_id = f"sbom:{attestation.sbom_id}"
        if self._vertex_exists(sbom_vertex_id):
            self._create_edge(
                EdgeLabel.ATTESTED_BY,
                sbom_vertex_id,
                vertex_id,
                {"created_at": attestation.created_at.isoformat()},
            )

        logger.info(f"Stored attestation {attestation.attestation_id}")
        return vertex_id

    def get_attestations_for_sbom(self, sbom_id: str) -> list[dict[str, Any]]:
        """Get all attestations for an SBOM.

        Args:
            sbom_id: SBOM identifier

        Returns:
            List of attestation properties
        """
        if self.mode == GraphMode.MOCK:
            results = []
            sbom_vertex_id = f"sbom:{sbom_id}"
            for edge in self._mock_edges.values():
                if (
                    edge.label == EdgeLabel.ATTESTED_BY
                    and edge.from_vertex_id == sbom_vertex_id
                ):
                    vertex = self._mock_vertices.get(edge.to_vertex_id)
                    if vertex:
                        results.append(vertex.properties)
            return results

        # AWS mode would use Gremlin query
        return []

    def link_superseding_attestation(
        self,
        new_attestation_id: str,
        old_attestation_id: str,
    ) -> None:
        """Link a new attestation as superseding an old one.

        Args:
            new_attestation_id: ID of the new attestation
            old_attestation_id: ID of the superseded attestation
        """
        new_vertex_id = f"attestation:{new_attestation_id}"
        old_vertex_id = f"attestation:{old_attestation_id}"

        self._create_edge(
            EdgeLabel.SUPERSEDES,
            new_vertex_id,
            old_vertex_id,
            {"superseded_at": datetime.now(timezone.utc).isoformat()},
        )

        logger.info(f"Attestation {new_attestation_id} supersedes {old_attestation_id}")

    # -------------------------------------------------------------------------
    # License Operations
    # -------------------------------------------------------------------------

    def _store_license(self, license_id: str) -> str:
        """Store a license in the graph.

        Args:
            license_id: SPDX license identifier

        Returns:
            Vertex ID of the stored license
        """
        vertex_id = f"license:{license_id}"

        # Check if already exists
        if self._vertex_exists(vertex_id):
            return vertex_id

        # Import here to avoid circular dependency
        from .license_engine import SPDX_LICENSES

        spdx_info = SPDX_LICENSES.get(license_id)

        if spdx_info:
            properties = {
                "spdx_id": spdx_info.id,
                "name": spdx_info.name,
                "category": spdx_info.category.value,
                "osi_approved": spdx_info.osi_approved,
                "fsf_free": spdx_info.fsf_free,
                "copyleft": spdx_info.copyleft,
            }
            if spdx_info.url:
                properties["url"] = spdx_info.url
        else:
            properties = {
                "spdx_id": license_id,
                "name": license_id,
                "category": LicenseCategory.UNKNOWN.value,
                "osi_approved": False,
                "fsf_free": False,
                "copyleft": False,
            }

        vertex = GraphVertex(
            id=vertex_id,
            label=VertexLabel.LICENSE,
            properties=properties,
        )

        self._upsert_vertex(vertex)
        return vertex_id

    def get_license_usage(self, license_id: str) -> list[dict[str, Any]]:
        """Get all dependencies using a specific license.

        Args:
            license_id: SPDX license identifier

        Returns:
            List of dependency properties
        """
        if self.mode == GraphMode.MOCK:
            results = []
            license_vertex_id = f"license:{license_id}"
            for edge in self._mock_edges.values():
                if (
                    edge.label == EdgeLabel.LICENSED_UNDER
                    and edge.to_vertex_id == license_vertex_id
                ):
                    vertex = self._mock_vertices.get(edge.from_vertex_id)
                    if vertex:
                        results.append(vertex.properties)
            return results

        # AWS mode would use Gremlin query
        return []

    # -------------------------------------------------------------------------
    # Provenance Queries
    # -------------------------------------------------------------------------

    def get_provenance_chain(self, purl: str) -> Optional[ProvenanceChain]:
        """Get the provenance chain for a package.

        Args:
            purl: Package URL

        Returns:
            ProvenanceChain with attestation history
        """
        vertex_id = f"dependency:{purl}"

        if not self._vertex_exists(vertex_id):
            return None

        # Find SBOMs containing this dependency
        sbom_ids = self._find_sboms_containing(vertex_id)

        # Find attestations for each SBOM
        attestations: list[dict[str, Any]] = []
        for sbom_id in sbom_ids:
            sbom_attestations = self.get_attestations_for_sbom(sbom_id)
            attestations.extend(sbom_attestations)

        # Sort by creation time
        attestations.sort(
            key=lambda a: a.get("created_at", ""),
            reverse=True,
        )

        if not attestations:
            return ProvenanceChain(
                package_url=purl,
                attestations=[],
                sbom_ids=sbom_ids,
                verified=False,
                verification_status=VerificationStatus.NOT_VERIFIED,
            )

        return ProvenanceChain(
            package_url=purl,
            attestations=attestations,
            sbom_ids=sbom_ids,
            verified=True,
            verification_status=VerificationStatus.VERIFIED,
            latest_attestation_id=attestations[0].get("attestation_id"),
            latest_attestation_at=datetime.fromisoformat(
                attestations[0].get(
                    "created_at", datetime.now(timezone.utc).isoformat()
                )
            ),
        )

    def _find_sboms_containing(self, dependency_vertex_id: str) -> list[str]:
        """Find SBOMs that contain a dependency.

        Args:
            dependency_vertex_id: Vertex ID of the dependency

        Returns:
            List of SBOM IDs
        """
        if self.mode == GraphMode.MOCK:
            sbom_ids = []
            for edge in self._mock_edges.values():
                if (
                    edge.label == EdgeLabel.CONTAINS
                    and edge.to_vertex_id == dependency_vertex_id
                ):
                    # Extract SBOM ID from vertex ID
                    sbom_vertex = self._mock_vertices.get(edge.from_vertex_id)
                    if sbom_vertex:
                        sbom_id = sbom_vertex.properties.get("sbom_id")
                        if sbom_id:
                            sbom_ids.append(sbom_id)
            return sbom_ids

        # AWS mode would use Gremlin traversal
        return []

    # -------------------------------------------------------------------------
    # Graph Operations
    # -------------------------------------------------------------------------

    def _upsert_vertex(self, vertex: GraphVertex) -> None:
        """Insert or update a vertex in the graph."""
        if self.mode == GraphMode.MOCK:
            self._mock_vertices[vertex.id] = vertex
            return

        if not self._client:
            raise GraphIntegrationError("Neptune client not initialized")

        # Build Gremlin query
        props = []
        for key, value in vertex.properties.items():
            escaped = escape_gremlin_string(str(value))
            props.append(f".property('{key}', '{escaped}')")

        query = (
            f"g.V('{vertex.id}').fold()"
            f".coalesce(unfold(), addV('{vertex.label.value}').property(id, '{vertex.id}'))"
            f"{''.join(props)}"
        )

        try:
            self._client.submit(query).all().result()
        except Exception as e:
            raise GraphIntegrationError(f"Failed to upsert vertex: {e}")

    def _get_vertex(self, vertex_id: str) -> Optional[GraphVertex]:
        """Get a vertex by ID."""
        if self.mode == GraphMode.MOCK:
            return self._mock_vertices.get(vertex_id)

        if not self._client:
            return None

        query = f"g.V('{vertex_id}').valueMap(true)"
        try:
            results = self._client.submit(query).all().result()
            if results:
                props = results[0]
                # Extract label from result
                label_str = props.pop("label", [VertexLabel.DEPENDENCY.value])[0]
                # Flatten single-value lists
                flat_props = {
                    k: v[0] if isinstance(v, list) and len(v) == 1 else v
                    for k, v in props.items()
                }
                return GraphVertex(
                    id=vertex_id,
                    label=VertexLabel(label_str),
                    properties=flat_props,
                )
        except Exception as e:
            logger.error(f"Failed to get vertex {vertex_id}: {e}")

        return None

    def _vertex_exists(self, vertex_id: str) -> bool:
        """Check if a vertex exists."""
        if self.mode == GraphMode.MOCK:
            return vertex_id in self._mock_vertices

        if not self._client:
            return False

        query = f"g.V('{vertex_id}').count()"
        try:
            results = self._client.submit(query).all().result()
            return results[0] > 0 if results else False
        except Exception:
            return False

    def _create_edge(
        self,
        label: EdgeLabel,
        from_vertex_id: str,
        to_vertex_id: str,
        properties: dict[str, Any],
    ) -> str:
        """Create an edge between two vertices."""
        edge_id = hashlib.sha256(
            f"{label.value}:{from_vertex_id}:{to_vertex_id}".encode()
        ).hexdigest()[:16]

        if self.mode == GraphMode.MOCK:
            edge = GraphEdge(
                id=edge_id,
                label=label,
                from_vertex_id=from_vertex_id,
                to_vertex_id=to_vertex_id,
                properties=properties,
            )
            self._mock_edges[edge_id] = edge
            return edge_id

        if not self._client:
            raise GraphIntegrationError("Neptune client not initialized")

        # Build Gremlin query
        props = []
        for key, value in properties.items():
            escaped = escape_gremlin_string(str(value))
            props.append(f".property('{key}', '{escaped}')")

        query = (
            f"g.V('{from_vertex_id}')"
            f".coalesce("
            f"  outE('{label.value}').where(inV().hasId('{to_vertex_id}')),"
            f"  addE('{label.value}').to(g.V('{to_vertex_id}'))"
            f")"
            f"{''.join(props)}"
        )

        try:
            self._client.submit(query).all().result()
        except Exception as e:
            raise GraphIntegrationError(f"Failed to create edge: {e}")

        return edge_id

    # -------------------------------------------------------------------------
    # Cleanup Operations
    # -------------------------------------------------------------------------

    def delete_sbom(self, sbom_id: str) -> bool:
        """Delete an SBOM and its relationships.

        Args:
            sbom_id: SBOM identifier

        Returns:
            True if deleted, False if not found
        """
        vertex_id = f"sbom:{sbom_id}"

        if self.mode == GraphMode.MOCK:
            if vertex_id not in self._mock_vertices:
                return False

            # Delete edges
            edges_to_delete = [
                eid
                for eid, edge in self._mock_edges.items()
                if edge.from_vertex_id == vertex_id or edge.to_vertex_id == vertex_id
            ]
            for eid in edges_to_delete:
                del self._mock_edges[eid]

            # Delete vertex
            del self._mock_vertices[vertex_id]
            return True

        if not self._client:
            return False

        query = f"g.V('{vertex_id}').drop()"
        try:
            self._client.submit(query).all().result()
            return True
        except Exception as e:
            logger.error(f"Failed to delete SBOM {sbom_id}: {e}")
            return False

    def close(self) -> None:
        """Close the graph client connection."""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning(f"Error closing Neptune client: {e}")
            self._client = None


# Singleton instance
_graph_instance: Optional[SupplyChainGraphService] = None


def get_supply_chain_graph_service() -> SupplyChainGraphService:
    """Get singleton graph service instance."""
    global _graph_instance
    if _graph_instance is None:
        config = get_supply_chain_config().storage
        mode = GraphMode.MOCK if config.use_mock_storage else GraphMode.AWS
        _graph_instance = SupplyChainGraphService(config=config, mode=mode)
    return _graph_instance


def reset_supply_chain_graph_service() -> None:
    """Reset graph service singleton (for testing)."""
    global _graph_instance
    if _graph_instance is not None:
        _graph_instance.close()
    _graph_instance = None
