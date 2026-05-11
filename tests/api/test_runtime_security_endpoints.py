"""Tests for ``src/api/runtime_security_endpoints.py`` (wave 3, #163).

The endpoints are stubs for now (Pydantic shapes locked in, bodies
return empty). These tests verify:

  - All 13 routes register and respond 200
  - Response shapes match the frontend ``runtimeSecurityApi.js``
    typedefs
  - Query parameters are accepted and don't crash
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.runtime_security_endpoints import router


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Wrap the router in a minimal FastAPI app for testing.

    Avoids importing ``src.api.main`` (which pulls in agents, DB
    services, monitoring, etc.) - the router is self-contained and
    should be testable in isolation.
    """
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Admission Controller
# ---------------------------------------------------------------------------


def test_admission_decisions_returns_well_formed_response(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/admission/decisions")

    assert r.status_code == 200
    body = r.json()
    assert "decisions" in body
    assert "summary" in body
    assert isinstance(body["decisions"], list)
    summary = body["summary"]
    assert set(summary) == {"allow_count", "deny_count", "warn_count", "total_24h"}


def test_admission_decisions_accepts_query_params(client: TestClient) -> None:
    r = client.get(
        "/api/v1/runtime-security/admission/decisions",
        params={"limit": 100, "namespace": "production"},
    )
    assert r.status_code == 200


def test_admission_decisions_rejects_bad_limit(client: TestClient) -> None:
    r = client.get(
        "/api/v1/runtime-security/admission/decisions",
        params={"limit": 9999},
    )
    assert r.status_code == 422


def test_admission_policies_returns_list(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/admission/policies")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_admission_stats_returns_full_shape(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/admission/stats")
    assert r.status_code == 200
    body = r.json()
    expected = {
        "decisions_24h",
        "deny_rate_pct",
        "warn_rate_pct",
        "avg_decision_latency_ms",
        "policies_active",
    }
    assert set(body) == expected


# ---------------------------------------------------------------------------
# Container escape
# ---------------------------------------------------------------------------


def test_escape_attempts_returns_list(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/container/escape-attempts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_container_anomalies_returns_list(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/container/anomalies")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_mitre_mapping_returns_list(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/container/mitre-mapping")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Runtime correlation
# ---------------------------------------------------------------------------


def test_runtime_correlation_returns_list(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/correlation")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_cloudtrail_events_returns_list(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/correlation/cloudtrail")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_code_correlations_returns_list(client: TestClient) -> None:
    r = client.get(
        "/api/v1/runtime-security/correlation/code",
        params={"min_confidence": 80},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# GuardDuty
# ---------------------------------------------------------------------------


def test_guardduty_findings_returns_list(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/guardduty/findings")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_guardduty_stats_returns_full_shape(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/guardduty/stats")
    assert r.status_code == 200
    body = r.json()
    expected = {
        "total_findings",
        "critical_count",
        "high_count",
        "medium_count",
        "low_count",
        "correlated_to_code_count",
        "archived_count",
    }
    assert set(body) == expected


def test_guardduty_code_links_returns_list(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/guardduty/code-links")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_returns_ok_with_iso_timestamp(client: TestClient) -> None:
    r = client.get("/api/v1/runtime-security/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # ISO 8601 timestamp; basic sanity check
    assert "T" in body["timestamp"]


# ---------------------------------------------------------------------------
# Coverage of frontend contract
# ---------------------------------------------------------------------------


def test_all_12_frontend_endpoints_register(client: TestClient) -> None:
    """The frontend ``ENDPOINTS`` map lists 12 URL paths; verify each
    one exists in our router so widgets stop 404ing."""
    expected_paths = {
        "/api/v1/runtime-security/admission/decisions",
        "/api/v1/runtime-security/admission/policies",
        "/api/v1/runtime-security/admission/stats",
        "/api/v1/runtime-security/container/escape-attempts",
        "/api/v1/runtime-security/container/anomalies",
        "/api/v1/runtime-security/container/mitre-mapping",
        "/api/v1/runtime-security/correlation",
        "/api/v1/runtime-security/correlation/cloudtrail",
        "/api/v1/runtime-security/correlation/code",
        "/api/v1/runtime-security/guardduty/findings",
        "/api/v1/runtime-security/guardduty/stats",
        "/api/v1/runtime-security/guardduty/code-links",
    }

    for path in expected_paths:
        r = client.get(path)
        assert r.status_code == 200, f"endpoint {path} did not return 200"
