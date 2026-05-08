"""Tests for ADR-090 Phase 5.3 ABAC filter."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.services.graph.edge_labels import EdgeLabel
from src.services.graph.phase5_abac_filter import (
    PHASE5_EDGE_LABELS,
    FilterDecision,
    FilterStats,
    apply_phase5_filter,
)

# -- Fakes -------------------------------------------------------------


@dataclass
class _RecordingAudit:
    decisions: list[FilterDecision]
    contexts: list[dict]

    def emit(self, decision, context):
        self.decisions.append(decision)
        self.contexts.append(context)


class _ToggleableKillSwitch:
    def __init__(self, active: bool):
        self.active = active

    def is_active(self) -> bool:
        return self.active


def _audit() -> _RecordingAudit:
    return _RecordingAudit(decisions=[], contexts=[])


def _edge(label: str, sensitivity: str | None = None, **extra) -> dict:
    edge = {"relationship": label, **extra}
    if sensitivity is not None:
        edge["sensitivity"] = sensitivity
    return edge


# -- Pass-through ------------------------------------------------------


class TestPassThrough:
    def test_non_phase5_edges_always_pass(self):
        edges = [
            _edge(EdgeLabel.CALLS.value),
            _edge(EdgeLabel.IMPORTS.value),
            _edge(EdgeLabel.CONTAINS.value),
        ]
        allowed, stats = apply_phase5_filter(edges, caller_clearance="internal")
        assert allowed == edges
        assert stats.edges_filtered == 0
        assert stats.phase5_edges_seen == 0


# -- Clearance comparison ----------------------------------------------


class TestClearanceFiltering:
    def test_internal_caller_blocked_from_restricted_edge(self):
        audit = _audit()
        edges = [_edge(EdgeLabel.USES_KMS_KEY.value, "restricted")]
        allowed, stats = apply_phase5_filter(
            edges, caller_clearance="internal", audit=audit
        )
        assert allowed == []
        assert stats.edges_filtered == 1
        assert audit.decisions[0].edge_label == EdgeLabel.USES_KMS_KEY.value
        assert audit.decisions[0].sensitivity == "restricted"
        assert audit.decisions[0].reason == "clearance_below_required"

    def test_restricted_caller_passes_restricted_edge(self):
        audit = _audit()
        edges = [_edge(EdgeLabel.USES_KMS_KEY.value, "restricted")]
        allowed, stats = apply_phase5_filter(
            edges, caller_clearance="restricted", audit=audit
        )
        assert allowed == edges
        assert stats.edges_filtered == 0
        assert audit.decisions == []

    def test_top_level_caller_passes_everything(self):
        edges = [
            _edge(EdgeLabel.USES_KMS_KEY.value, "restricted"),
            _edge(EdgeLabel.READS_CONFIG.value, "restricted"),
            _edge(EdgeLabel.DEPENDS_ON_ENV.value, "confidential"),
            _edge(EdgeLabel.FEATURE_GATED_BY.value, "confidential"),
        ]
        allowed, stats = apply_phase5_filter(edges, caller_clearance="top_level")
        assert allowed == edges
        assert stats.edges_filtered == 0

    def test_internal_caller_passes_confidential_blocked_at_restricted(self):
        """Sally's tiering boundary: env+flag are confidential, kms+ssm are restricted."""
        edges = [
            _edge(EdgeLabel.DEPENDS_ON_ENV.value, "confidential"),
            _edge(EdgeLabel.FEATURE_GATED_BY.value, "confidential"),
            _edge(EdgeLabel.READS_CONFIG.value, "restricted"),
            _edge(EdgeLabel.USES_KMS_KEY.value, "restricted"),
        ]
        allowed, stats = apply_phase5_filter(edges, caller_clearance="confidential")
        # confidential caller passes confidential edges, blocks restricted.
        assert len(allowed) == 2
        assert all(e["sensitivity"] == "confidential" for e in allowed)
        assert stats.edges_filtered == 2

    def test_metadata_nested_sensitivity_supported(self):
        edges = [
            {
                "relationship": EdgeLabel.READS_CONFIG.value,
                "metadata": {"sensitivity": "restricted"},
            }
        ]
        allowed, stats = apply_phase5_filter(edges, caller_clearance="internal")
        assert allowed == []
        assert stats.edges_filtered == 1


# -- Fail-closed default -----------------------------------------------


class TestFailClosed:
    def test_missing_sensitivity_treated_as_top_level(self):
        audit = _audit()
        edges = [{"relationship": EdgeLabel.USES_KMS_KEY.value}]
        allowed, stats = apply_phase5_filter(
            edges, caller_clearance="restricted", audit=audit
        )
        # Even a restricted caller cannot reach top_level by default.
        assert allowed == []
        assert stats.fail_closed_defaults_applied == 1
        assert stats.edges_filtered == 1

    def test_unknown_sensitivity_treated_as_top_level(self):
        edges = [_edge(EdgeLabel.READS_CONFIG.value, "extraterrestrial")]
        allowed, stats = apply_phase5_filter(edges, caller_clearance="restricted")
        # The unknown level resolves to top_level via _rank fallback.
        assert allowed == []
        assert stats.edges_filtered == 1


# -- Kill switch -------------------------------------------------------


class TestKillSwitch:
    def test_inactive_switch_uses_written_sensitivity(self):
        kill = _ToggleableKillSwitch(active=False)
        edges = [_edge(EdgeLabel.DEPENDS_ON_ENV.value, "confidential")]
        allowed, stats = apply_phase5_filter(
            edges,
            caller_clearance="confidential",
            kill_switch=kill,
        )
        assert allowed == edges
        assert stats.kill_switch_active is False

    def test_active_switch_forces_top_level_on_every_phase5_edge(self):
        kill = _ToggleableKillSwitch(active=True)
        audit = _audit()
        edges = [
            _edge(EdgeLabel.DEPENDS_ON_ENV.value, "confidential"),
            _edge(EdgeLabel.FEATURE_GATED_BY.value, "confidential"),
        ]
        allowed, stats = apply_phase5_filter(
            edges,
            caller_clearance="restricted",
            audit=audit,
            kill_switch=kill,
        )
        assert allowed == []
        assert stats.kill_switch_active is True
        assert all(d.reason == "kill_switch" for d in audit.decisions)
        assert all(d.sensitivity == "top_level" for d in audit.decisions)

    def test_active_switch_lets_top_level_caller_through(self):
        kill = _ToggleableKillSwitch(active=True)
        edges = [_edge(EdgeLabel.DEPENDS_ON_ENV.value, "confidential")]
        allowed, _ = apply_phase5_filter(
            edges,
            caller_clearance="top_level",
            kill_switch=kill,
        )
        assert allowed == edges


# -- Audit context -----------------------------------------------------


class TestAuditContext:
    def test_audit_emits_supplied_context(self):
        audit = _audit()
        edges = [_edge(EdgeLabel.USES_KMS_KEY.value, "restricted")]
        apply_phase5_filter(
            edges,
            caller_clearance="internal",
            audit=audit,
            audit_context={
                "user_id": "u-1",
                "session_id": "s-1",
                "query_intent": "incident_triage",
            },
        )
        assert audit.contexts == [
            {
                "user_id": "u-1",
                "session_id": "s-1",
                "query_intent": "incident_triage",
            }
        ]

    def test_audit_failure_does_not_break_filter(self):
        class _Boom:
            def emit(self, decision, context):
                raise RuntimeError("audit sink down")

        edges = [_edge(EdgeLabel.USES_KMS_KEY.value, "restricted")]
        # Filtering proceeds despite audit failures.
        allowed, stats = apply_phase5_filter(
            edges, caller_clearance="internal", audit=_Boom()
        )
        assert allowed == []
        assert stats.edges_filtered == 1


# -- Telemetry contract ------------------------------------------------


class TestTelemetry:
    def test_stats_count_seen_phase5_and_filtered(self):
        edges = [
            _edge(EdgeLabel.CALLS.value),
            _edge(EdgeLabel.READS_CONFIG.value, "restricted"),
            _edge(EdgeLabel.DEPENDS_ON_ENV.value, "confidential"),
        ]
        _, stats = apply_phase5_filter(edges, caller_clearance="internal")
        assert stats.edges_seen == 3
        assert stats.phase5_edges_seen == 2
        # Both phase5 edges are above internal -> filtered.
        assert stats.edges_filtered == 2

    def test_filterstats_default_zero(self):
        s = FilterStats()
        assert s.edges_seen == 0
        assert s.phase5_edges_seen == 0
        assert s.edges_filtered == 0
        assert s.kill_switch_active is False
        assert s.fail_closed_defaults_applied == 0


# -- Closed-set contract -----------------------------------------------


class TestPhase5LabelSet:
    def test_set_matches_canonical_phase5_edges(self):
        assert PHASE5_EDGE_LABELS == {
            EdgeLabel.READS_CONFIG.value,
            EdgeLabel.DEPENDS_ON_ENV.value,
            EdgeLabel.USES_KMS_KEY.value,
            EdgeLabel.FEATURE_GATED_BY.value,
        }
