"""Per-process recent-events history for runtime-security widgets (Wave 5a, #163).

The audit's wave-3 runtime-security FastAPI router shipped 12 endpoints
backed by empty stubs (``TODO(#163-wave4)``). The behind-the-scenes
services (``AdmissionController``, ``ContainerEscapeDetector``,
``RuntimeCodeCorrelator``, ``GuardDuty`` integration) are event-driven
- they process incoming events but don't expose "give me the last N
decisions" today.

This module fills that gap with a bounded in-memory deque per event
type. Each service pushes to the store on its happy path; the API
handlers read from it. Bounded so a long-lived pod doesn't accumulate
unbounded state; durable history belongs in CloudWatch Logs Insights
or Neptune (the latter wired in commit 3929913).

The store is intentionally minimal:

  - Per-process. Cross-pod state stays out of scope; durable history
    lives in Neptune via ``RuntimeSecurityGraphService``.
  - Threadsafe via a single ``threading.Lock``.
  - Items are typed only via ``dict[str, Any]`` so each service can
    push whatever shape its widget contract expects without coupling
    the store to the contract module.

Author: Project Aura Team
Created: 2026-05-11
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any, Deque, Optional

logger = logging.getLogger(__name__)


_DEFAULT_HISTORY_CAP = 500


class RuntimeSecurityHistoryStore:
    """Bounded per-process history of recent runtime-security events.

    Construct one instance per process; the API handlers read from the
    singleton via ``get_history_store()``. Production wiring will push
    to it from the admission controller, escape detector, correlator,
    and GuardDuty ingestion paths as their event handlers fire.
    """

    def __init__(self, capacity: int = _DEFAULT_HISTORY_CAP) -> None:
        self._capacity = capacity
        self._lock = threading.Lock()
        # One deque per public bucket the runtime-security API exposes.
        self._admission_decisions: Deque[dict[str, Any]] = deque(maxlen=capacity)
        self._admission_policies: list[dict[str, Any]] = []
        self._escape_attempts: Deque[dict[str, Any]] = deque(maxlen=capacity)
        self._container_anomalies: Deque[dict[str, Any]] = deque(maxlen=capacity)
        self._correlations: Deque[dict[str, Any]] = deque(maxlen=capacity)
        self._cloudtrail_events: Deque[dict[str, Any]] = deque(maxlen=capacity)
        self._code_correlations: Deque[dict[str, Any]] = deque(maxlen=capacity)
        self._guardduty_findings: Deque[dict[str, Any]] = deque(maxlen=capacity)
        # Rollup counters incremented alongside the per-event pushes.
        self._admission_counters: dict[str, int] = {
            "allow_count": 0,
            "deny_count": 0,
            "warn_count": 0,
            "total_24h": 0,
        }

    @property
    def capacity(self) -> int:
        return self._capacity

    # ---------------------------------------------------------------
    # Push side - services call these on event ingestion
    # ---------------------------------------------------------------

    def record_admission_decision(self, decision: dict[str, Any]) -> None:
        with self._lock:
            self._admission_decisions.appendleft(decision)
            choice = (decision.get("decision") or "").upper()
            if choice == "ALLOW":
                self._admission_counters["allow_count"] += 1
            elif choice == "DENY":
                self._admission_counters["deny_count"] += 1
            elif choice == "WARN":
                self._admission_counters["warn_count"] += 1
            self._admission_counters["total_24h"] += 1

    def set_admission_policies(self, policies: list[dict[str, Any]]) -> None:
        with self._lock:
            self._admission_policies = list(policies)

    def record_escape_attempt(self, attempt: dict[str, Any]) -> None:
        with self._lock:
            self._escape_attempts.appendleft(attempt)

    def record_container_anomaly(self, anomaly: dict[str, Any]) -> None:
        with self._lock:
            self._container_anomalies.appendleft(anomaly)

    def record_correlation(self, correlation: dict[str, Any]) -> None:
        with self._lock:
            self._correlations.appendleft(correlation)

    def record_cloudtrail_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._cloudtrail_events.appendleft(event)

    def record_code_correlation(self, correlation: dict[str, Any]) -> None:
        with self._lock:
            self._code_correlations.appendleft(correlation)

    def record_guardduty_finding(self, finding: dict[str, Any]) -> None:
        with self._lock:
            self._guardduty_findings.appendleft(finding)

    # ---------------------------------------------------------------
    # Read side - API handlers call these
    # ---------------------------------------------------------------

    def list_admission_decisions(
        self,
        limit: int = 50,
        namespace: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            decisions = list(self._admission_decisions)
        if namespace:
            decisions = [d for d in decisions if d.get("namespace") == namespace]
        return decisions[:limit]

    def admission_summary(self) -> dict[str, int]:
        with self._lock:
            return dict(self._admission_counters)

    def list_admission_policies(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._admission_policies)

    def admission_stats(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(self._admission_counters)
            policy_count = len(self._admission_policies)
            decision_count = len(self._admission_decisions)
        total = max(counters["total_24h"], 1)
        return {
            "decisions_24h": counters["total_24h"],
            "deny_rate_pct": round(counters["deny_count"] / total * 100, 2),
            "warn_rate_pct": round(counters["warn_count"] / total * 100, 2),
            "avg_decision_latency_ms": 0.0,  # populated by emitter
            "policies_active": policy_count,
            "recent_decisions_in_buffer": decision_count,
        }

    def list_escape_attempts(
        self,
        limit: int = 50,
        severity: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            attempts = list(self._escape_attempts)
        if severity:
            sev = severity.lower()
            attempts = [a for a in attempts if (a.get("severity") or "").lower() == sev]
        return attempts[:limit]

    def list_container_anomalies(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._container_anomalies)[:limit]

    def mitre_mapping_rollup(self) -> list[dict[str, Any]]:
        with self._lock:
            attempts = list(self._escape_attempts)
        counts: dict[tuple[str, str, str], int] = {}
        for a in attempts:
            tid = a.get("mitre_technique") or ""
            tname = a.get("technique") or ""
            tactic = a.get("mitre_tactic") or ""
            if tid:
                counts[(tid, tname, tactic)] = counts.get((tid, tname, tactic), 0) + 1
        return [
            {
                "technique_id": tid,
                "technique_name": tname,
                "tactic": tactic,
                "detection_count": count,
            }
            for (tid, tname, tactic), count in sorted(
                counts.items(), key=lambda kv: -kv[1]
            )
        ]

    def list_correlations(
        self,
        limit: int = 50,
        min_confidence: int = 50,
    ) -> list[dict[str, Any]]:
        with self._lock:
            corrs = list(self._correlations)
        if min_confidence > 0:
            corrs = [c for c in corrs if c.get("confidence_score", 0) >= min_confidence]
        return corrs[:limit]

    def list_cloudtrail_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._cloudtrail_events)[:limit]

    def list_code_correlations(
        self, limit: int = 50, min_confidence: int = 50
    ) -> list[dict[str, Any]]:
        with self._lock:
            corrs = list(self._code_correlations)
        if min_confidence > 0:
            corrs = [c for c in corrs if c.get("confidence", 0) >= min_confidence]
        return corrs[:limit]

    def list_guardduty_findings(
        self,
        limit: int = 50,
        severity: Optional[str] = None,
        archived: bool = False,
    ) -> list[dict[str, Any]]:
        with self._lock:
            findings = list(self._guardduty_findings)
        findings = [f for f in findings if bool(f.get("archived", False)) == archived]
        if severity:
            sev = severity.lower()
            findings = [f for f in findings if (f.get("severity") or "").lower() == sev]
        return findings[:limit]

    def guardduty_stats(self) -> dict[str, int]:
        with self._lock:
            findings = list(self._guardduty_findings)
        stats = {
            "total_findings": len(findings),
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "correlated_to_code_count": 0,
            "archived_count": 0,
        }
        for f in findings:
            sev = (f.get("severity") or "").lower()
            if sev == "critical":
                stats["critical_count"] += 1
            elif sev == "high":
                stats["high_count"] += 1
            elif sev == "medium":
                stats["medium_count"] += 1
            elif sev == "low":
                stats["low_count"] += 1
            if f.get("code_link"):
                stats["correlated_to_code_count"] += 1
            if f.get("archived"):
                stats["archived_count"] += 1
        return stats

    def list_guardduty_code_links(
        self,
        limit: int = 50,
        min_confidence: int = 50,
    ) -> list[dict[str, Any]]:
        with self._lock:
            findings = list(self._guardduty_findings)
        out: list[dict[str, Any]] = []
        for f in findings:
            link = f.get("code_link")
            if link is None:
                continue
            confidence = int(f.get("correlation_confidence", 80))
            if confidence < min_confidence:
                continue
            out.append(
                {
                    "finding_id": f.get("finding_id"),
                    "finding_type": f.get("type"),
                    "code_link": link,
                    "confidence": confidence,
                }
            )
        return out[:limit]

    # ---------------------------------------------------------------
    # Test helpers
    # ---------------------------------------------------------------

    def clear(self) -> None:
        """Drop all buffered events. Test hook."""
        with self._lock:
            self._admission_decisions.clear()
            self._admission_policies.clear()
            self._escape_attempts.clear()
            self._container_anomalies.clear()
            self._correlations.clear()
            self._cloudtrail_events.clear()
            self._code_correlations.clear()
            self._guardduty_findings.clear()
            for k in self._admission_counters:
                self._admission_counters[k] = 0


_INSTANCE: Optional[RuntimeSecurityHistoryStore] = None


def get_history_store() -> RuntimeSecurityHistoryStore:
    """Process-singleton accessor."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = RuntimeSecurityHistoryStore()
    return _INSTANCE


def reset_history_store(
    replacement: Optional[RuntimeSecurityHistoryStore] = None,
) -> None:
    """Test hook: swap or clear the singleton."""
    global _INSTANCE
    _INSTANCE = replacement
