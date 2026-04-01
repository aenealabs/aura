"""
Project Aura - Capability Graph Synchronization Service

Synchronizes agent capability policies with the Neptune graph database.
Minimal ADR-070 component required for ADR-071 graph analysis.

Security Rationale:
- Graph state reflects current policy configuration
- Event-driven sync ensures consistency
- Audit trail for all graph modifications

Author: Project Aura Team
Created: 2026-01-27
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .contracts import ToolClassification
from .graph_contracts import EdgeType, VertexType
from .policy import AgentCapabilityPolicy
from .registry import get_capability_registry

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Status of a graph synchronization operation."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Some updates failed
    FAILED = "failed"
    SKIPPED = "skipped"  # No changes needed


@dataclass
class PolicyDeployedEvent:
    """
    Event emitted when a capability policy is deployed.

    Triggers graph synchronization to update Neptune with current policy state.
    """

    event_id: str
    policy_name: str
    policy_version: str
    agent_type: str
    deployed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deployed_by: str = "system"
    environment: str = "development"
    changes_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "agent_type": self.agent_type,
            "deployed_at": self.deployed_at.isoformat(),
            "deployed_by": self.deployed_by,
            "environment": self.environment,
            "changes_summary": self.changes_summary,
        }


@dataclass
class SyncResult:
    """
    Result of a graph synchronization operation.

    Contains metrics and any errors encountered during sync.
    """

    sync_id: str
    status: SyncStatus
    vertices_created: int = 0
    vertices_updated: int = 0
    vertices_deleted: int = 0
    edges_created: int = 0
    edges_updated: int = 0
    edges_deleted: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "sync_id": self.sync_id,
            "status": self.status.value,
            "vertices_created": self.vertices_created,
            "vertices_updated": self.vertices_updated,
            "vertices_deleted": self.vertices_deleted,
            "edges_created": self.edges_created,
            "edges_updated": self.edges_updated,
            "edges_deleted": self.edges_deleted,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_ms": self.duration_ms,
            "errors": self.errors,
        }

    @property
    def total_changes(self) -> int:
        """Total number of graph modifications."""
        return (
            self.vertices_created
            + self.vertices_updated
            + self.vertices_deleted
            + self.edges_created
            + self.edges_updated
            + self.edges_deleted
        )


class PolicyGraphSynchronizer:
    """
    Synchronizes capability policies with the Neptune graph database.

    Maintains the capability graph in sync with deployed policies,
    enabling ADR-071 graph analysis queries.

    Usage:
        >>> sync = PolicyGraphSynchronizer()
        >>> event = PolicyDeployedEvent(
        ...     event_id="evt-123",
        ...     policy_name="coder-policy",
        ...     policy_version="1.0.0",
        ...     agent_type="CoderAgent",
        ... )
        >>> result = await sync.on_policy_deployed(event)
        >>> print(f"Synced {result.total_changes} changes")
    """

    def __init__(
        self,
        neptune_service: Optional[Any] = None,
        mock_mode: bool = True,
    ):
        """
        Initialize the policy graph synchronizer.

        Args:
            neptune_service: Optional NeptuneGraphService instance
            mock_mode: If True, use in-memory mock graph
        """
        self.neptune_service = neptune_service
        self.mock_mode = mock_mode or neptune_service is None

        # In-memory graph for mock mode
        self._mock_vertices: dict[str, dict[str, Any]] = {}
        self._mock_edges: list[dict[str, Any]] = []

        # Sync history for audit
        self._sync_history: list[SyncResult] = []

        logger.info(f"PolicyGraphSynchronizer initialized (mock_mode={self.mock_mode})")

    async def on_policy_deployed(self, event: PolicyDeployedEvent) -> SyncResult:
        """
        Handle policy deployment event.

        Synchronizes the agent's capabilities to the graph database.

        Args:
            event: Policy deployment event

        Returns:
            SyncResult with metrics and status
        """
        sync_id = f"sync-{uuid.uuid4().hex[:12]}"
        result = SyncResult(sync_id=sync_id, status=SyncStatus.SUCCESS)

        logger.info(
            f"Processing policy deployment: {event.policy_name} v{event.policy_version}"
        )

        try:
            # Get the policy for this agent type
            policy = AgentCapabilityPolicy.for_agent_type(event.agent_type)

            # Sync agent vertex
            agent_vertex_result = await self._sync_agent_vertex(
                event.agent_type, policy
            )
            result.vertices_created += agent_vertex_result.get("created", 0)
            result.vertices_updated += agent_vertex_result.get("updated", 0)

            # Sync capability edges
            capability_result = await self._sync_capability_edges(
                event.agent_type, policy
            )
            result.edges_created += capability_result.get("created", 0)
            result.edges_updated += capability_result.get("updated", 0)
            result.edges_deleted += capability_result.get("deleted", 0)

            # Sync context restrictions
            context_result = await self._sync_context_restrictions(
                event.agent_type, policy
            )
            result.edges_created += context_result.get("created", 0)

            result.completed_at = datetime.now(timezone.utc)
            result.duration_ms = (
                result.completed_at - result.started_at
            ).total_seconds() * 1000

            logger.info(
                f"Policy sync completed: {result.total_changes} changes in "
                f"{result.duration_ms:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Policy sync failed: {e}")
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))
            result.completed_at = datetime.now(timezone.utc)

        self._sync_history.append(result)
        return result

    async def sync_agent_capabilities(
        self,
        agent_name: str,
        policy: AgentCapabilityPolicy,
    ) -> SyncResult:
        """
        Sync a single agent's capabilities to the graph.

        Args:
            agent_name: Name of the agent
            policy: Agent's capability policy

        Returns:
            SyncResult with metrics
        """
        event = PolicyDeployedEvent(
            event_id=f"manual-{uuid.uuid4().hex[:8]}",
            policy_name=f"{agent_name.lower()}-policy",
            policy_version=policy.version,
            agent_type=policy.agent_type,
        )
        return await self.on_policy_deployed(event)

    async def sync_all_policies(self) -> SyncResult:
        """
        Sync all known agent policies to the graph.

        Useful for initial graph population or full reconciliation.

        Returns:
            Aggregated SyncResult
        """
        sync_id = f"bulk-{uuid.uuid4().hex[:12]}"
        result = SyncResult(sync_id=sync_id, status=SyncStatus.SUCCESS)

        # Known agent types
        agent_types = [
            "CoderAgent",
            "ReviewerAgent",
            "ValidatorAgent",
            "MetaOrchestrator",
            "RedTeamAgent",
            "AdminAgent",
        ]

        for agent_type in agent_types:
            try:
                policy = AgentCapabilityPolicy.for_agent_type(agent_type)
                sub_result = await self.sync_agent_capabilities(agent_type, policy)

                result.vertices_created += sub_result.vertices_created
                result.vertices_updated += sub_result.vertices_updated
                result.edges_created += sub_result.edges_created
                result.edges_updated += sub_result.edges_updated
                result.edges_deleted += sub_result.edges_deleted
                result.errors.extend(sub_result.errors)

            except Exception as e:
                logger.error(f"Failed to sync {agent_type}: {e}")
                result.errors.append(f"{agent_type}: {str(e)}")

        if result.errors:
            result.status = SyncStatus.PARTIAL

        result.completed_at = datetime.now(timezone.utc)
        result.duration_ms = (
            result.completed_at - result.started_at
        ).total_seconds() * 1000

        return result

    async def _sync_agent_vertex(
        self,
        agent_type: str,
        policy: AgentCapabilityPolicy,
    ) -> dict[str, int]:
        """Create or update agent vertex in graph."""
        vertex_id = f"agent:{agent_type}"
        metrics = {"created": 0, "updated": 0}

        vertex_data = {
            "id": vertex_id,
            "type": VertexType.AGENT.value,
            "label": agent_type,
            "agent_type": agent_type,
            "policy_version": policy.version,
            "can_elevate_children": policy.can_elevate_children,
            "default_decision": policy.default_decision.value,
            "global_rate_limit": policy.global_rate_limit,
            "allowed_contexts": list(policy.allowed_contexts),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if self.mock_mode:
            if vertex_id in self._mock_vertices:
                metrics["updated"] = 1
            else:
                metrics["created"] = 1
            self._mock_vertices[vertex_id] = vertex_data
        else:
            # Real Neptune upsert
            await self._upsert_vertex(vertex_data)
            metrics["updated"] = 1  # Upsert counts as update

        return metrics

    async def _sync_capability_edges(
        self,
        agent_type: str,
        policy: AgentCapabilityPolicy,
    ) -> dict[str, int]:
        """Sync HAS_CAPABILITY edges from agent to tools."""
        agent_vertex_id = f"agent:{agent_type}"
        metrics = {"created": 0, "updated": 0, "deleted": 0}

        # Get registry for tool classifications
        registry = get_capability_registry()

        # Current capabilities from policy
        current_tools = set(policy.allowed_tools.keys())

        # Existing edges in mock mode
        if self.mock_mode:
            existing_edges = [
                e
                for e in self._mock_edges
                if e["source_id"] == agent_vertex_id
                and e["edge_type"] == EdgeType.HAS_CAPABILITY.value
            ]
            existing_tools = {
                e["target_id"].replace("cap:", "") for e in existing_edges
            }

            # Delete removed capabilities
            for tool in existing_tools - current_tools:
                self._mock_edges = [
                    e
                    for e in self._mock_edges
                    if not (
                        e["source_id"] == agent_vertex_id
                        and e["target_id"] == f"cap:{tool}"
                    )
                ]
                metrics["deleted"] += 1

        # Add/update current capabilities
        for tool_name, actions in policy.allowed_tools.items():
            tool_info = registry.get_tool(tool_name)
            classification = (
                tool_info.classification if tool_info else ToolClassification.SAFE
            )

            # Ensure capability vertex exists
            cap_vertex_id = f"cap:{tool_name}"
            cap_vertex_data = {
                "id": cap_vertex_id,
                "type": VertexType.CAPABILITY.value,
                "label": tool_name,
                "tool_name": tool_name,
                "classification": classification.value,
            }

            if self.mock_mode:
                if cap_vertex_id not in self._mock_vertices:
                    self._mock_vertices[cap_vertex_id] = cap_vertex_data

            # Create edge
            edge_id = self._generate_edge_id(
                agent_vertex_id, cap_vertex_id, EdgeType.HAS_CAPABILITY
            )
            edge_data = {
                "id": edge_id,
                "edge_type": EdgeType.HAS_CAPABILITY.value,
                "source_id": agent_vertex_id,
                "target_id": cap_vertex_id,
                "actions": actions,
                "classification": classification.value,
            }

            if self.mock_mode:
                # Check if edge exists
                existing = next(
                    (e for e in self._mock_edges if e["id"] == edge_id),
                    None,
                )
                if existing:
                    # Update
                    existing.update(edge_data)
                    metrics["updated"] += 1
                else:
                    # Create
                    self._mock_edges.append(edge_data)
                    metrics["created"] += 1

        return metrics

    async def _sync_context_restrictions(
        self,
        agent_type: str,
        policy: AgentCapabilityPolicy,
    ) -> dict[str, int]:
        """Sync RESTRICTED_TO edges for context restrictions."""
        agent_vertex_id = f"agent:{agent_type}"
        metrics = {"created": 0}

        for context in policy.allowed_contexts:
            # Ensure context vertex exists
            context_vertex_id = f"context:{context}"
            context_vertex_data = {
                "id": context_vertex_id,
                "type": VertexType.CONTEXT.value,
                "label": context,
                "context_name": context,
            }

            if self.mock_mode:
                if context_vertex_id not in self._mock_vertices:
                    self._mock_vertices[context_vertex_id] = context_vertex_data

                # Create edge if not exists
                edge_id = self._generate_edge_id(
                    agent_vertex_id, context_vertex_id, EdgeType.RESTRICTED_TO
                )
                existing = next(
                    (e for e in self._mock_edges if e["id"] == edge_id),
                    None,
                )
                if not existing:
                    self._mock_edges.append(
                        {
                            "id": edge_id,
                            "edge_type": EdgeType.RESTRICTED_TO.value,
                            "source_id": agent_vertex_id,
                            "target_id": context_vertex_id,
                        }
                    )
                    metrics["created"] += 1

        return metrics

    async def _upsert_vertex(self, vertex_data: dict[str, Any]) -> None:
        """Upsert a vertex in Neptune (real mode only)."""
        if self.neptune_service is None:
            return

        # Build Gremlin upsert query
        # This would use neptune_service.execute_query() in production
        logger.debug(f"Would upsert vertex: {vertex_data['id']}")

    def _generate_edge_id(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
    ) -> str:
        """Generate deterministic edge ID for idempotent operations."""
        content = f"{source_id}|{target_id}|{edge_type.value}"
        return f"edge:{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    def get_mock_graph(self) -> dict[str, Any]:
        """Get the current mock graph state (for testing)."""
        return {
            "vertices": self._mock_vertices.copy(),
            "edges": self._mock_edges.copy(),
        }

    def get_sync_history(self) -> list[SyncResult]:
        """Get history of sync operations."""
        return self._sync_history.copy()


# Singleton instance
_synchronizer: Optional[PolicyGraphSynchronizer] = None


def get_policy_graph_synchronizer() -> PolicyGraphSynchronizer:
    """Get the singleton PolicyGraphSynchronizer instance."""
    global _synchronizer
    if _synchronizer is None:
        _synchronizer = PolicyGraphSynchronizer()
    return _synchronizer


def reset_policy_graph_synchronizer() -> None:
    """Reset the singleton instance (for testing)."""
    global _synchronizer
    _synchronizer = None
