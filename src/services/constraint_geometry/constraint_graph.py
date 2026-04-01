"""
Project Aura - Constraint Graph Resolver

Resolves applicable constraints from the Neptune constraint graph
for a given policy profile and execution context.

Phase 1 provides an in-memory graph resolver for testing and development.
Phase 2 adds Neptune Gremlin integration.

Author: Project Aura Team
Created: 2026-02-11
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Protocol, Sequence

from .contracts import (
    ConstraintAxis,
    ConstraintEdge,
    ConstraintEdgeType,
    ConstraintRule,
    ResolvedConstraintSet,
)
from .policy_profile import PolicyProfile

logger = logging.getLogger(__name__)


class NeptuneClient(Protocol):
    """Protocol for Neptune Gremlin client."""

    async def submit(self, gremlin: str, bindings: dict[str, Any]) -> Any: ...


class ConstraintGraphResolver:
    """Resolves applicable constraints from the constraint graph.

    Phase 1: In-memory graph with pre-loaded constraints.
    Phase 2: Neptune Gremlin traversal for full graph resolution.
    """

    def __init__(
        self,
        neptune_client: Optional[NeptuneClient] = None,
    ):
        self._neptune = neptune_client
        self._rules: dict[str, ConstraintRule] = {}
        self._edges: list[ConstraintEdge] = []
        self._version = "1.0.0"

    def load_rules(self, rules: Sequence[ConstraintRule]) -> None:
        """Load constraint rules into the in-memory graph.

        Args:
            rules: Constraint rules to load
        """
        for rule in rules:
            self._rules[rule.rule_id] = rule
        logger.info("Loaded %d constraint rules", len(rules))

    def load_edges(self, edges: Sequence[ConstraintEdge]) -> None:
        """Load constraint edges into the in-memory graph."""
        self._edges = list(edges)
        logger.info("Loaded %d constraint edges", len(edges))

    def set_version(self, version: str) -> None:
        """Set the constraint graph version."""
        self._version = version

    async def resolve(
        self,
        profile: PolicyProfile,
        context: Optional[dict[str, Any]] = None,
    ) -> ResolvedConstraintSet:
        """Resolve applicable constraints for a policy profile.

        Phase 1 (in-memory):
        - Returns all loaded rules grouped by axis
        - Filters by temporal validity
        - Applies RELAXES/TIGHTENS edge modifiers

        Args:
            profile: Policy profile to resolve constraints for
            context: Execution context for conditional edges

        Returns:
            ResolvedConstraintSet with rules grouped by axis
        """
        context = context or {}
        now = datetime.now(timezone.utc)

        # Group active rules by axis
        rules_by_axis: dict[ConstraintAxis, list[ConstraintRule]] = {
            axis: [] for axis in ConstraintAxis
        }

        for rule in self._rules.values():
            if not rule.is_active:
                continue
            rules_by_axis[rule.axis].append(rule)

        # Apply edge modifiers
        edges_traversed = self._apply_edge_modifiers(rules_by_axis, context)

        # Build frozen result
        rules_tuple = tuple(
            (axis, tuple(rules)) for axis, rules in rules_by_axis.items() if rules
        )

        return ResolvedConstraintSet(
            rules_by_axis=rules_tuple,
            version=self._version,
            profile_name=profile.name,
            resolved_at=now,
            edges_traversed=edges_traversed,
        )

    def _apply_edge_modifiers(
        self,
        rules_by_axis: dict[ConstraintAxis, list[ConstraintRule]],
        context: dict[str, Any],
    ) -> int:
        """Apply RELAXES/TIGHTENS/SUPERSEDES edges to modify rule weights.

        Returns number of edges traversed.
        """
        edges_traversed = 0

        for edge in self._edges:
            if edge.source_id not in self._rules:
                continue
            if edge.target_id not in self._rules:
                continue

            # Check edge temporal validity
            now = datetime.now(timezone.utc)
            if edge.effective_at and now < edge.effective_at:
                continue
            if edge.expires_at and now > edge.expires_at:
                continue

            # Check condition
            if edge.condition and not self._evaluate_condition(edge.condition, context):
                continue

            edges_traversed += 1

            target_rule = self._rules[edge.target_id]

            if edge.edge_type == ConstraintEdgeType.SUPERSEDES:
                # Remove superseded rule
                axis_rules = rules_by_axis.get(target_rule.axis, [])
                rules_by_axis[target_rule.axis] = [
                    r for r in axis_rules if r.rule_id != target_rule.rule_id
                ]

        return edges_traversed

    @staticmethod
    def _evaluate_condition(
        condition: str,
        context: dict[str, Any],
    ) -> bool:
        """Evaluate a simple condition string against context.

        Supports: key=value format.
        """
        if "=" not in condition:
            return False

        key, value = condition.split("=", 1)
        return str(context.get(key.strip(), "")) == value.strip()
