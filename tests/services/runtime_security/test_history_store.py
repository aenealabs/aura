"""Tests for ``runtime_security.history_store`` (Wave 5a, #163).

The history store is a per-process bounded deque that the 12 wave-3
runtime-security API handlers read from. These tests cover the
push/read semantics, filtering, capacity bounds, MITRE rollup, and
GuardDuty stats aggregation.
"""

from __future__ import annotations

import pytest

from src.services.runtime_security.history_store import (
    RuntimeSecurityHistoryStore,
    get_history_store,
    reset_history_store,
)


@pytest.fixture
def store() -> RuntimeSecurityHistoryStore:
    return RuntimeSecurityHistoryStore(capacity=10)


# ---------------------------------------------------------------------------
# Admission
# ---------------------------------------------------------------------------


def test_record_decision_updates_counter_and_buffer(store) -> None:
    store.record_admission_decision({"decision": "ALLOW", "namespace": "default"})
    store.record_admission_decision({"decision": "DENY", "namespace": "default"})
    store.record_admission_decision({"decision": "WARN", "namespace": "default"})

    summary = store.admission_summary()
    assert summary == {
        "allow_count": 1,
        "deny_count": 1,
        "warn_count": 1,
        "total_24h": 3,
    }
    decisions = store.list_admission_decisions(limit=10)
    assert len(decisions) == 3
    # Newest first
    assert decisions[0]["decision"] == "WARN"


def test_list_decisions_filters_by_namespace(store) -> None:
    store.record_admission_decision({"decision": "ALLOW", "namespace": "default"})
    store.record_admission_decision({"decision": "DENY", "namespace": "production"})

    only_prod = store.list_admission_decisions(namespace="production")

    assert len(only_prod) == 1
    assert only_prod[0]["namespace"] == "production"


def test_admission_stats_computes_percentages(store) -> None:
    for _ in range(10):
        store.record_admission_decision({"decision": "ALLOW"})
    for _ in range(5):
        store.record_admission_decision({"decision": "DENY"})

    stats = store.admission_stats()

    assert stats["decisions_24h"] == 15
    assert stats["deny_rate_pct"] == round(5 / 15 * 100, 2)


def test_set_policies_replaces_list(store) -> None:
    store.set_admission_policies([{"policy_id": "p1", "name": "a"}])
    store.set_admission_policies([{"policy_id": "p2", "name": "b"}])

    listed = store.list_admission_policies()
    assert len(listed) == 1
    assert listed[0]["policy_id"] == "p2"


# ---------------------------------------------------------------------------
# Escape attempts + MITRE
# ---------------------------------------------------------------------------


def test_list_escape_attempts_filters_by_severity(store) -> None:
    store.record_escape_attempt({"severity": "critical", "mitre_technique": "T1611"})
    store.record_escape_attempt({"severity": "low", "mitre_technique": "T1011"})

    crit = store.list_escape_attempts(severity="critical")

    assert len(crit) == 1
    assert crit[0]["severity"] == "critical"


def test_mitre_rollup_counts_techniques(store) -> None:
    for _ in range(3):
        store.record_escape_attempt(
            {
                "mitre_technique": "T1611",
                "technique": "Mount /etc/shadow",
                "mitre_tactic": "Privilege Escalation",
            }
        )
    store.record_escape_attempt(
        {
            "mitre_technique": "T1068",
            "technique": "Dirty Pipe",
            "mitre_tactic": "Privilege Escalation",
        }
    )

    rollup = store.mitre_mapping_rollup()

    # Sorted by count desc -> T1611 first
    assert rollup[0]["technique_id"] == "T1611"
    assert rollup[0]["detection_count"] == 3
    assert rollup[1]["technique_id"] == "T1068"
    assert rollup[1]["detection_count"] == 1


# ---------------------------------------------------------------------------
# Correlation + cloudtrail + code
# ---------------------------------------------------------------------------


def test_list_correlations_filters_by_min_confidence(store) -> None:
    store.record_correlation({"correlation_id": "c1", "confidence_score": 80})
    store.record_correlation({"correlation_id": "c2", "confidence_score": 40})

    high_only = store.list_correlations(min_confidence=70)

    assert len(high_only) == 1
    assert high_only[0]["correlation_id"] == "c1"


def test_list_code_correlations_filters_by_confidence(store) -> None:
    store.record_code_correlation({"correlation_id": "x", "confidence": 90})
    store.record_code_correlation({"correlation_id": "y", "confidence": 30})

    listed = store.list_code_correlations(min_confidence=60)
    assert {c["correlation_id"] for c in listed} == {"x"}


def test_cloudtrail_buffer_returns_newest_first(store) -> None:
    store.record_cloudtrail_event({"event_id": "1"})
    store.record_cloudtrail_event({"event_id": "2"})
    store.record_cloudtrail_event({"event_id": "3"})

    listed = store.list_cloudtrail_events()
    assert [e["event_id"] for e in listed] == ["3", "2", "1"]


# ---------------------------------------------------------------------------
# GuardDuty
# ---------------------------------------------------------------------------


def test_guardduty_stats_aggregates_by_severity(store) -> None:
    store.record_guardduty_finding({"severity": "Critical"})
    store.record_guardduty_finding({"severity": "Critical"})
    store.record_guardduty_finding({"severity": "Low"})
    store.record_guardduty_finding({"severity": "High", "code_link": {"file": "x.py"}})
    store.record_guardduty_finding({"severity": "Medium", "archived": True})

    stats = store.guardduty_stats()

    assert stats["total_findings"] == 5
    assert stats["critical_count"] == 2
    assert stats["high_count"] == 1
    assert stats["medium_count"] == 1
    assert stats["low_count"] == 1
    assert stats["correlated_to_code_count"] == 1
    assert stats["archived_count"] == 1


def test_guardduty_findings_filter_archived(store) -> None:
    store.record_guardduty_finding({"finding_id": "1", "archived": False})
    store.record_guardduty_finding({"finding_id": "2", "archived": True})

    active = store.list_guardduty_findings(archived=False)
    archived = store.list_guardduty_findings(archived=True)

    assert [f["finding_id"] for f in active] == ["1"]
    assert [f["finding_id"] for f in archived] == ["2"]


def test_guardduty_code_links_only_emits_findings_with_link(store) -> None:
    store.record_guardduty_finding(
        {
            "finding_id": "1",
            "type": "SSHBruteForce",
            "code_link": {"file": "x.py", "line": 1},
            "correlation_confidence": 85,
        }
    )
    store.record_guardduty_finding({"finding_id": "2", "code_link": None})
    store.record_guardduty_finding(
        {
            "finding_id": "3",
            "type": "Recon",
            "code_link": {"file": "y.py", "line": 2},
            "correlation_confidence": 20,
        }
    )

    links = store.list_guardduty_code_links(min_confidence=50)

    assert [l["finding_id"] for l in links] == ["1"]


# ---------------------------------------------------------------------------
# Capacity bound
# ---------------------------------------------------------------------------


def test_buffer_caps_at_configured_capacity() -> None:
    store = RuntimeSecurityHistoryStore(capacity=3)
    for i in range(10):
        store.record_admission_decision({"decision": "ALLOW", "namespace": str(i)})

    decisions = store.list_admission_decisions(limit=100)
    assert len(decisions) == 3
    # Newest first; the last 3 pushes survived
    assert [d["namespace"] for d in decisions] == ["9", "8", "7"]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_singleton_accessor_returns_same_instance() -> None:
    reset_history_store()
    a = get_history_store()
    b = get_history_store()
    assert a is b


def test_reset_history_store_replaces_singleton() -> None:
    custom = RuntimeSecurityHistoryStore()
    reset_history_store(custom)
    assert get_history_store() is custom
    reset_history_store(None)
    assert get_history_store() is not custom


def test_clear_drops_all_buffers() -> None:
    store = RuntimeSecurityHistoryStore()
    store.record_admission_decision({"decision": "ALLOW"})
    store.record_escape_attempt({"severity": "high"})

    store.clear()

    assert store.list_admission_decisions() == []
    assert store.list_escape_attempts() == []
    assert store.admission_summary()["total_24h"] == 0
