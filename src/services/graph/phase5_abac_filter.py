"""Phase 5 ABAC filter for graph traversal results (ADR-090).

Implements Pattern A enforcement (edge-property filter, hardened) per
ADR-090 Thread 4. Every Phase 5 edge carries a ``sensitivity``
property; the filter compares the caller's :class:`ClearanceLevel`
to the edge's required clearance and excludes any edge above it.

Design choices, all from Sally's review:

  - **Single chokepoint.** All graph callers must filter through
    :func:`apply_phase5_filter` (or the wrapper in
    ``context_retrieval_service``); a contract test prevents new
    code paths from reaching :meth:`NeptuneGraphService.find_related_code`
    without going through here. Bypass is the failure mode the
    review explicitly called out.
  - **Fail-closed default.** Any edge whose ``sensitivity`` property
    is missing or unrecognized is treated as ``TOP_LEVEL``, the
    highest required clearance. The ADR-090 contract is that
    Phase 5 edge writers always set the property; missing property
    indicates either a producer bug or a malicious write. Either
    way we deny.
  - **Silent filter + audit log.** Filtered edges are removed
    silently from results; the caller does not learn the edges
    existed. Every filtered edge emits an ADR-072 anomaly hook
    (via the supplied audit sink) so a low-clearance principal
    repeatedly traversing near restricted edges shows up as
    reconnaissance behaviour.
  - **SSM-toggleable kill-switch.** A boolean SSM parameter (read
    via the supplied :class:`KillSwitchProvider`) can globally
    force every Phase 5 edge to ``TOP_LEVEL`` regardless of its
    written sensitivity. Incident response toggle, not a code
    deploy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from src.services.graph.edge_labels import EdgeLabel

logger = logging.getLogger(__name__)


# Phase 5 edge labels -- the closed set the filter inspects.
PHASE5_EDGE_LABELS: frozenset[str] = frozenset(
    {
        EdgeLabel.READS_CONFIG.value,
        EdgeLabel.DEPENDS_ON_ENV.value,
        EdgeLabel.USES_KMS_KEY.value,
        EdgeLabel.FEATURE_GATED_BY.value,
    }
)


# Sensitivity ordering. Mirrors the ADR-073 ClearanceLevel ordering;
# we intentionally do not import the deployed enum here so this
# module stays free of circular imports against the authorization
# package. The tuple ordering is the canonical ranking and is the
# single place to add a new tier.
SENSITIVITY_RANK: dict[str, int] = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
    "top_level": 4,
}


def _rank(level: str) -> int:
    """Return the numeric rank of a sensitivity / clearance string.

    Unknown values resolve to TOP_LEVEL so a malformed property
    never lowers the access bar (fail-closed default).
    """
    return SENSITIVITY_RANK.get(level, SENSITIVITY_RANK["top_level"])


@dataclass
class FilterDecision:
    """Outcome of running the filter over a single edge."""

    allowed: bool
    edge_label: str
    sensitivity: str
    required_clearance: str
    reason: str


@dataclass
class FilterStats:
    """Per-call telemetry for the filter."""

    edges_seen: int = 0
    phase5_edges_seen: int = 0
    edges_filtered: int = 0
    kill_switch_active: bool = False
    fail_closed_defaults_applied: int = 0


class AuditSink(Protocol):
    """Audit emitter used when filter denies a Phase 5 edge.

    Production wires this to ADR-072 anomaly detector + immutable
    S3 audit log; tests pass a recording fake.
    """

    def emit(self, decision: FilterDecision, context: dict[str, Any]) -> None: ...


class KillSwitchProvider(Protocol):
    """Reads the SSM-backed Phase 5 kill switch.

    Production reads the SSM parameter at startup and refreshes on
    a background interval; tests inject a fake.
    """

    def is_active(self) -> bool: ...


class _NoopAuditSink:
    def emit(self, decision: FilterDecision, context: dict[str, Any]) -> None:
        return


class _DisabledKillSwitch:
    def is_active(self) -> bool:
        return False


def apply_phase5_filter(
    edges: Iterable[dict[str, Any]],
    *,
    caller_clearance: str,
    audit: AuditSink | None = None,
    kill_switch: KillSwitchProvider | None = None,
    audit_context: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], FilterStats]:
    """Return ``edges`` minus any Phase 5 edge above caller's clearance.

    Args:
        edges: Iterable of edge dicts (Gremlin valueMap shape or the
            mock graph's edge dict). Each must carry a ``relationship``
            key; Phase 5 edges additionally carry ``sensitivity``
            (or ``metadata.sensitivity`` for nested forms).
        caller_clearance: One of the Phase 5 sensitivity strings
            (``public``..``top_level``). Sourced from the caller's
            :class:`SubjectAttributes` per ADR-073.
        audit: Optional audit sink invoked once per filtered edge.
        kill_switch: Optional kill-switch provider; when active,
            every Phase 5 edge is treated as ``top_level`` regardless
            of written sensitivity.
        audit_context: Optional dict of caller metadata (user_id,
            session_id, query_intent) attached to every audit
            emission.

    Returns:
        ``(allowed_edges, stats)`` -- the filtered edge list plus
        per-call telemetry. The input is never mutated; the returned
        list contains the same edge dicts that passed the filter.
    """
    audit = audit or _NoopAuditSink()
    kill_switch = kill_switch or _DisabledKillSwitch()
    audit_context = dict(audit_context or {})

    stats = FilterStats(kill_switch_active=kill_switch.is_active())
    caller_rank = _rank(caller_clearance)

    allowed: list[dict[str, Any]] = []
    for edge in edges:
        stats.edges_seen += 1
        label = edge.get("relationship")
        if label not in PHASE5_EDGE_LABELS:
            allowed.append(edge)
            continue

        stats.phase5_edges_seen += 1
        sensitivity = _resolve_edge_sensitivity(edge)
        if sensitivity is None:
            stats.fail_closed_defaults_applied += 1
            sensitivity = "top_level"

        required_rank = _rank(sensitivity)
        if stats.kill_switch_active:
            required_rank = _rank("top_level")
            sensitivity = "top_level"

        if caller_rank >= required_rank:
            allowed.append(edge)
            continue

        # Filtered: emit audit, do not surface to caller.
        decision = FilterDecision(
            allowed=False,
            edge_label=label,
            sensitivity=sensitivity,
            required_clearance=sensitivity,
            reason=(
                "kill_switch"
                if stats.kill_switch_active
                else "clearance_below_required"
            ),
        )
        try:
            audit.emit(decision, audit_context)
        except Exception as e:  # pragma: no cover - audit failures must not leak
            logger.warning(f"Phase 5 ABAC audit emission failed: {e}")
        stats.edges_filtered += 1

    return allowed, stats


def _resolve_edge_sensitivity(edge: dict[str, Any]) -> str | None:
    """Extract the sensitivity string from an edge dict.

    Supports both the flat ``edge["sensitivity"]`` shape (mock-mode
    edges) and the Gremlin-shaped ``edge["metadata"]["sensitivity"]``
    that real Neptune valueMap responses carry.
    """
    if "sensitivity" in edge and isinstance(edge["sensitivity"], str):
        return edge["sensitivity"]
    metadata = edge.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("sensitivity")
        if isinstance(value, str):
            return value
    return None
