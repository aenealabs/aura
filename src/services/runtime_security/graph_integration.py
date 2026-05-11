"""
Project Aura - Runtime Security Graph Integration

Neptune graph database integration for runtime security data including:
- RuntimeEvent vertices
- AWSResource vertices
- IaCResource vertices
- ContainerImage vertices
- AdmissionDecision vertices

Based on ADR-077: Cloud Runtime Security Integration
"""

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .config import RuntimeSecurityConfig, get_runtime_security_config
from .contracts import (
    AdmissionDecision,
    AWSResource,
    ContainerImage,
    CorrelationResult,
    EscapeEvent,
    IaCResource,
    ResourceMapping,
    RuntimeEvent,
)

logger = logging.getLogger(__name__)


class VertexLabel(Enum):
    """Neptune vertex labels for runtime security."""

    RUNTIME_EVENT = "RuntimeEvent"
    AWS_RESOURCE = "AWSResource"
    IAC_RESOURCE = "IaCResource"
    CONTAINER_IMAGE = "ContainerImage"
    ADMISSION_DECISION = "AdmissionDecision"
    ESCAPE_EVENT = "EscapeEvent"
    CODE_FILE = "CodeFile"


class EdgeLabel(Enum):
    """Neptune edge labels for runtime security."""

    TRIGGERED_BY = "TRIGGERED_BY"
    DEFINED_IN = "DEFINED_IN"
    SOURCE_CODE = "SOURCE_CODE"
    RUNS_IMAGE = "RUNS_IMAGE"
    ESCAPE_ATTEMPT_FROM = "ESCAPE_ATTEMPT_FROM"
    ADMISSION_FOR = "ADMISSION_FOR"
    CORRELATED_TO = "CORRELATED_TO"


@dataclass
class GraphVertex:
    """Represents a Neptune vertex."""

    vertex_id: str
    label: VertexLabel
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Represents a Neptune edge."""

    edge_id: str
    label: EdgeLabel
    from_vertex_id: str
    to_vertex_id: str
    properties: dict[str, Any] = field(default_factory=dict)


def escape_gremlin_string(value: str) -> str:
    """Escape a string for use in Gremlin queries."""
    if not value:
        return value
    # Escape backslashes first, then quotes, then newlines
    value = value.replace("\\", "\\\\")
    value = value.replace("'", "\\'")
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    value = value.replace("\t", "\\t")
    return value


class RuntimeSecurityGraphService:
    """
    Neptune graph service for runtime security data.

    Manages vertices and edges for:
    - Runtime events (CloudTrail, GuardDuty, Falco)
    - AWS resources
    - IaC resource definitions
    - Container images
    - Admission decisions
    - Escape events
    """

    def __init__(
        self,
        config: Optional[RuntimeSecurityConfig] = None,
        neptune_client: Optional[Any] = None,
    ):
        """Initialize graph service with configuration.

        Args:
            config: Runtime-security config. Loaded from env if None.
            neptune_client: Optional thread-dispatched Gremlin client
                (the ``.client`` attribute from
                ``NeptuneGraphService``). When provided AND the config
                does not select mock mode, ``_store_vertex`` and
                ``_create_edge`` issue real Gremlin writes. When None
                or mock-mode is on, both paths use the in-memory mock
                dict.
        """
        self._config = config or get_runtime_security_config()
        self._use_mock = self._config.graph.use_mock or neptune_client is None

        # Mock storage for testing
        self._mock_vertices: dict[str, GraphVertex] = {}
        self._mock_edges: dict[str, GraphEdge] = {}

        # Gremlin client (thread-dispatched ``.submit().all().result()``
        # API matching ``NeptuneGraphService.client``). None in mock mode.
        self._neptune_client = neptune_client if not self._use_mock else None

    def _get_connection(self):
        """Get Neptune connection."""
        if self._use_mock:
            return None
        return self._neptune_client

    def close(self) -> None:
        """Close Neptune connection.

        No-op when the client is owned externally; the
        ``NeptuneGraphService`` that built it is responsible for
        teardown. Kept for API compatibility with the old contract.
        """
        self._neptune_client = None

    # Store methods

    def store_runtime_event(self, event: RuntimeEvent) -> str:
        """Store a runtime event in the graph."""
        vertex_id = f"event:{event.event_id}"

        vertex = GraphVertex(
            vertex_id=vertex_id,
            label=VertexLabel.RUNTIME_EVENT,
            properties={
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "severity": event.severity.name,
                "aws_account_id": event.aws_account_id,
                "region": event.region,
                "timestamp": event.timestamp.isoformat(),
                "resource_arn": event.resource_arn,
                "description": event.description,
                "correlation_status": event.correlation_status.value,
                "code_path": event.code_path,
                "code_owner": event.code_owner,
                "mitre_attack_id": event.mitre_attack_id,
            },
        )

        self._store_vertex(vertex)

        # Create edge to AWS resource if present
        if event.resource_arn:
            resource_vertex_id = f"resource:{event.resource_arn}"
            if resource_vertex_id in self._mock_vertices or not self._use_mock:
                self._create_edge(
                    EdgeLabel.TRIGGERED_BY,
                    vertex_id,
                    resource_vertex_id,
                    {"correlation_confidence": 0.9},
                )

        logger.debug(f"Stored runtime event vertex: {vertex_id}")
        return vertex_id

    def store_aws_resource(self, resource: AWSResource) -> str:
        """Store an AWS resource in the graph."""
        vertex_id = f"resource:{resource.resource_arn}"

        vertex = GraphVertex(
            vertex_id=vertex_id,
            label=VertexLabel.AWS_RESOURCE,
            properties={
                "resource_arn": resource.resource_arn,
                "resource_type": resource.resource_type.value,
                "name": resource.name,
                "aws_account_id": resource.aws_account_id,
                "region": resource.region,
                "created_at": (
                    resource.created_at.isoformat() if resource.created_at else None
                ),
                "last_seen": (
                    resource.last_seen.isoformat() if resource.last_seen else None
                ),
                "tags": str(resource.tags),
            },
        )

        self._store_vertex(vertex)
        logger.debug(f"Stored AWS resource vertex: {vertex_id}")
        return vertex_id

    def store_iac_resource(self, resource: IaCResource) -> str:
        """Store an IaC resource in the graph."""
        vertex_id = f"iac:{resource.iac_resource_id}"

        vertex = GraphVertex(
            vertex_id=vertex_id,
            label=VertexLabel.IAC_RESOURCE,
            properties={
                "iac_resource_id": resource.iac_resource_id,
                "resource_type": resource.resource_type,
                "provider": resource.provider.value,
                "file_path": resource.file_path,
                "line_number": resource.line_number,
                "module": resource.module,
                "resource_name": resource.resource_name,
                "git_commit": resource.git_commit,
                "git_blame_author": resource.git_blame_author,
            },
        )

        self._store_vertex(vertex)

        # Create edge to code file
        if resource.file_path:
            code_vertex_id = f"code:{resource.file_path}"
            self._ensure_code_file_vertex(code_vertex_id, resource.file_path)
            self._create_edge(
                EdgeLabel.SOURCE_CODE,
                vertex_id,
                code_vertex_id,
                {
                    "line_start": resource.line_number,
                    "line_end": resource.line_number + 20,
                },
            )

        logger.debug(f"Stored IaC resource vertex: {vertex_id}")
        return vertex_id

    def store_container_image(self, image: ContainerImage) -> str:
        """Store a container image in the graph."""
        vertex_id = f"image:{image.digest}"

        vertex = GraphVertex(
            vertex_id=vertex_id,
            label=VertexLabel.CONTAINER_IMAGE,
            properties={
                "digest": image.digest,
                "repository": image.repository,
                "tag": image.tag,
                "sbom_id": image.sbom_id,
                "signed": image.signed,
                "signature_verified": image.signature_verified,
                "scanned_at": (
                    image.scanned_at.isoformat() if image.scanned_at else None
                ),
                "vulnerabilities": str(image.vulnerabilities),
            },
        )

        self._store_vertex(vertex)
        logger.debug(f"Stored container image vertex: {vertex_id}")
        return vertex_id

    def store_admission_decision(self, decision: AdmissionDecision) -> str:
        """Store an admission decision in the graph."""
        vertex_id = f"admission:{decision.decision_id}"

        vertex = GraphVertex(
            vertex_id=vertex_id,
            label=VertexLabel.ADMISSION_DECISION,
            properties={
                "decision_id": decision.decision_id,
                "request_uid": decision.request_uid,
                "cluster": decision.cluster,
                "namespace": decision.namespace,
                "resource_kind": decision.resource_kind,
                "resource_name": decision.resource_name,
                "decision": decision.decision.value,
                "violation_count": decision.violation_count,
                "timestamp": decision.timestamp.isoformat(),
                "latency_ms": decision.latency_ms,
            },
        )

        self._store_vertex(vertex)

        # Create edges to images that were checked
        for image_ref in decision.images_checked:
            image_vertex_id = f"image:{image_ref}"
            if image_vertex_id in self._mock_vertices or not self._use_mock:
                self._create_edge(
                    EdgeLabel.ADMISSION_FOR,
                    vertex_id,
                    image_vertex_id,
                )

        logger.debug(f"Stored admission decision vertex: {vertex_id}")
        return vertex_id

    def store_escape_event(self, event: EscapeEvent) -> str:
        """Store an escape event in the graph."""
        vertex_id = f"escape:{event.event_id}"

        vertex = GraphVertex(
            vertex_id=vertex_id,
            label=VertexLabel.ESCAPE_EVENT,
            properties={
                "event_id": event.event_id,
                "cluster": event.cluster,
                "node_id": event.node_id,
                "container_id": event.container_id,
                "pod_name": event.pod_name,
                "namespace": event.namespace,
                "technique": event.technique.value,
                "severity": event.severity.name,
                "syscall": event.syscall,
                "process_name": event.process_name,
                "blocked": event.blocked,
                "mitre_attack_id": event.mitre_attack_id,
                "falco_rule": event.falco_rule,
                "timestamp": event.timestamp.isoformat(),
            },
        )

        self._store_vertex(vertex)

        # Create edge to container image if present
        if event.image_digest:
            image_vertex_id = f"image:{event.image_digest}"
            self._create_edge(
                EdgeLabel.ESCAPE_ATTEMPT_FROM,
                vertex_id,
                image_vertex_id,
                {
                    "technique": event.technique.value,
                    "mitre_id": event.mitre_attack_id,
                },
            )

        logger.debug(f"Stored escape event vertex: {vertex_id}")
        return vertex_id

    def store_correlation(self, result: CorrelationResult) -> str:
        """Store a correlation result with edges."""
        # Ensure vertices exist
        if result.aws_resource:
            self.store_aws_resource(result.aws_resource)

        if result.iac_resource:
            self.store_iac_resource(result.iac_resource)

            # Link AWS resource to IaC
            if result.aws_resource:
                self._create_edge(
                    EdgeLabel.DEFINED_IN,
                    f"resource:{result.aws_resource.resource_arn}",
                    f"iac:{result.iac_resource.iac_resource_id}",
                    {"confidence": result.confidence},
                )

        return f"correlation:{result.event_id}"

    def store_resource_mapping(self, mapping: ResourceMapping) -> str:
        """Store a resource mapping with edges."""
        # Create or update AWS resource vertex
        aws_vertex_id = f"resource:{mapping.aws_resource_arn}"

        # Create IaC resource vertex
        iac_resource = IaCResource(
            iac_resource_id=mapping.iac_resource_id,
            resource_type="",
            provider=mapping.iac_provider,
            file_path=mapping.iac_file_path,
            line_number=1,
            git_commit=mapping.git_commit,
        )
        self.store_iac_resource(iac_resource)

        # Create edge
        self._create_edge(
            EdgeLabel.DEFINED_IN,
            aws_vertex_id,
            f"iac:{mapping.iac_resource_id}",
            {
                "terraform_state_key": mapping.terraform_state_key,
                "last_applied": (
                    mapping.last_applied.isoformat() if mapping.last_applied else None
                ),
                "confidence": mapping.confidence,
            },
        )

        return aws_vertex_id

    # Query methods

    def get_runtime_event(self, event_id: str) -> Optional[dict[str, Any]]:
        """Get a runtime event by ID."""
        vertex_id = f"event:{event_id}"
        return self._get_vertex_properties(vertex_id)

    def get_aws_resource(self, resource_arn: str) -> Optional[dict[str, Any]]:
        """Get an AWS resource by ARN."""
        vertex_id = f"resource:{resource_arn}"
        return self._get_vertex_properties(vertex_id)

    def get_container_image(self, digest: str) -> Optional[dict[str, Any]]:
        """Get a container image by digest."""
        vertex_id = f"image:{digest}"
        return self._get_vertex_properties(vertex_id)

    def get_events_for_resource(self, resource_arn: str) -> list[dict[str, Any]]:
        """Get all events triggered by a resource."""
        if self._use_mock:
            events = []
            for edge in self._mock_edges.values():
                if (
                    edge.label == EdgeLabel.TRIGGERED_BY
                    and edge.to_vertex_id == f"resource:{resource_arn}"
                ):
                    event_props = self._get_vertex_properties(edge.from_vertex_id)
                    if event_props:
                        events.append(event_props)
            return events

        # Would execute Gremlin query in production
        return []

    def get_escape_events_for_image(self, image_digest: str) -> list[dict[str, Any]]:
        """Get all escape events for a container image."""
        if self._use_mock:
            events = []
            for edge in self._mock_edges.values():
                if (
                    edge.label == EdgeLabel.ESCAPE_ATTEMPT_FROM
                    and edge.to_vertex_id == f"image:{image_digest}"
                ):
                    event_props = self._get_vertex_properties(edge.from_vertex_id)
                    if event_props:
                        events.append(event_props)
            return events

        return []

    def get_admission_decisions_for_image(
        self, image_digest: str
    ) -> list[dict[str, Any]]:
        """Get all admission decisions for a container image."""
        if self._use_mock:
            decisions = []
            for edge in self._mock_edges.values():
                if (
                    edge.label == EdgeLabel.ADMISSION_FOR
                    and edge.to_vertex_id == f"image:{image_digest}"
                ):
                    decision_props = self._get_vertex_properties(edge.from_vertex_id)
                    if decision_props:
                        decisions.append(decision_props)
            return decisions

        return []

    def get_iac_for_resource(self, resource_arn: str) -> Optional[dict[str, Any]]:
        """Get IaC definition for an AWS resource."""
        if self._use_mock:
            for edge in self._mock_edges.values():
                if (
                    edge.label == EdgeLabel.DEFINED_IN
                    and edge.from_vertex_id == f"resource:{resource_arn}"
                ):
                    return self._get_vertex_properties(edge.to_vertex_id)

        return None

    def delete_runtime_event(self, event_id: str) -> bool:
        """Delete a runtime event and its edges."""
        vertex_id = f"event:{event_id}"
        return self._delete_vertex(vertex_id)

    def delete_escape_event(self, event_id: str) -> bool:
        """Delete an escape event and its edges."""
        vertex_id = f"escape:{event_id}"
        return self._delete_vertex(vertex_id)

    # Internal methods

    def _store_vertex(self, vertex: GraphVertex) -> None:
        """Store a vertex in the graph.

        In mock mode, keeps the vertex in ``_mock_vertices``. In live
        mode, issues a Gremlin upsert (``g.V(id).fold().coalesce(
        unfold(), addV(label).property(id, ...))``) so repeated
        ``_store_vertex`` calls are idempotent. Properties are added
        with ``property(single, key, value)`` to overwrite any prior
        value rather than appending.
        """
        if self._use_mock:
            self._mock_vertices[vertex.vertex_id] = vertex
            return

        if self._neptune_client is None:
            # Defensive: live mode without a client. Fall back to mock
            # and log so the caller can spot the misconfiguration.
            logger.warning(
                "RuntimeSecurityGraphService in live mode without a "
                "Gremlin client; vertex %s buffered in mock dict",
                vertex.vertex_id,
            )
            self._mock_vertices[vertex.vertex_id] = vertex
            return

        vid = escape_gremlin_string(vertex.vertex_id)
        label = escape_gremlin_string(vertex.label.value)
        prop_clauses = [
            f".property(single, '{escape_gremlin_string(str(k))}', "
            f"'{escape_gremlin_string(str(v))}')"
            for k, v in vertex.properties.items()
        ]
        prop_chain = "".join(prop_clauses)
        query = (
            f"g.V().has('{label}', 'vertex_id', '{vid}')"
            f".fold()"
            f".coalesce(unfold(), addV('{label}').property(id, '{vid}')"
            f".property(single, 'vertex_id', '{vid}'))"
            f"{prop_chain}"
        )
        try:
            self._neptune_client.submit(query).all().result()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Neptune upsert failed for vertex %s (label=%s): %s",
                vertex.vertex_id,
                vertex.label.value,
                exc,
            )
            raise

    def _get_vertex_properties(self, vertex_id: str) -> Optional[dict[str, Any]]:
        """Get properties of a vertex."""
        if self._use_mock:
            vertex = self._mock_vertices.get(vertex_id)
            if vertex:
                return vertex.properties.copy()
            return None

        # Would execute Gremlin g.V().has('id', vertex_id).valueMap()
        return None

    def _delete_vertex(self, vertex_id: str) -> bool:
        """Delete a vertex and its edges."""
        if self._use_mock:
            if vertex_id in self._mock_vertices:
                del self._mock_vertices[vertex_id]
                # Delete edges
                edges_to_delete = [
                    eid
                    for eid, edge in self._mock_edges.items()
                    if edge.from_vertex_id == vertex_id
                    or edge.to_vertex_id == vertex_id
                ]
                for eid in edges_to_delete:
                    del self._mock_edges[eid]
                return True
            return False

        return False

    def _create_edge(
        self,
        label: EdgeLabel,
        from_vertex_id: str,
        to_vertex_id: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create an edge between two vertices."""
        edge_id = f"edge-{uuid.uuid4().hex[:12]}"

        edge = GraphEdge(
            edge_id=edge_id,
            label=label,
            from_vertex_id=from_vertex_id,
            to_vertex_id=to_vertex_id,
            properties=properties or {},
        )

        if self._use_mock:
            self._mock_edges[edge_id] = edge
            return edge_id

        if self._neptune_client is None:
            logger.warning(
                "RuntimeSecurityGraphService in live mode without a "
                "Gremlin client; edge %s buffered in mock dict",
                edge_id,
            )
            self._mock_edges[edge_id] = edge
            return edge_id

        from_vid = escape_gremlin_string(from_vertex_id)
        to_vid = escape_gremlin_string(to_vertex_id)
        elabel = escape_gremlin_string(label.value)
        eid = escape_gremlin_string(edge_id)
        prop_clauses = [
            f".property('{escape_gremlin_string(str(k))}', "
            f"'{escape_gremlin_string(str(v))}')"
            for k, v in (properties or {}).items()
        ]
        prop_chain = "".join(prop_clauses)
        # Edge upserts are harder than vertex upserts in Gremlin -
        # there's no shared idiom across providers. We rely on the
        # uniquely-generated edge_id as the natural anti-duplication
        # key (callers pass us a fresh id every time). If the same
        # caller wants idempotent edge writes they should generate a
        # deterministic edge_id and check `find_edges_for_vertex`
        # before calling.
        query = (
            f"g.V().has('vertex_id', '{from_vid}').as('a')"
            f".V().has('vertex_id', '{to_vid}').as('b')"
            f".addE('{elabel}').from('a').to('b')"
            f".property(id, '{eid}')"
            f".property('edge_id', '{eid}')"
            f"{prop_chain}"
        )
        try:
            self._neptune_client.submit(query).all().result()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Neptune addE failed for edge %s (label=%s, %s -> %s): %s",
                edge_id,
                label.value,
                from_vertex_id,
                to_vertex_id,
                exc,
            )
            raise
        return edge_id

    def _ensure_code_file_vertex(self, vertex_id: str, file_path: str) -> None:
        """Ensure a code file vertex exists."""
        if vertex_id not in self._mock_vertices:
            vertex = GraphVertex(
                vertex_id=vertex_id,
                label=VertexLabel.CODE_FILE,
                properties={"file_path": file_path},
            )
            self._store_vertex(vertex)


# Singleton instance
_graph_service_instance: Optional[RuntimeSecurityGraphService] = None


def get_runtime_security_graph_service() -> RuntimeSecurityGraphService:
    """Get singleton graph service instance."""
    global _graph_service_instance
    if _graph_service_instance is None:
        _graph_service_instance = RuntimeSecurityGraphService()
    return _graph_service_instance


def reset_runtime_security_graph_service() -> None:
    """Reset graph service singleton (for testing)."""
    global _graph_service_instance
    if _graph_service_instance is not None:
        _graph_service_instance.close()
    _graph_service_instance = None
