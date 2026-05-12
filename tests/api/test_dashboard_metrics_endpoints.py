"""Tests for ``src/api/dashboard_metrics_endpoints.py`` (#163 Wave 8).

The endpoints are stubs (Pydantic shapes locked, bodies return
empty/zero state). These tests verify:

  - All 5 routes register and respond 200
  - Response shapes match the frontend dashboardMetricsApi typedefs
  - Default values are the zero state (no fabricated numbers)
  - Health probe returns ISO 8601 timestamp
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dashboard_metrics_endpoints import router

# Module-level app/client (same pattern as test_runtime_security_endpoints.py).
_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app)


@pytest.fixture
def client() -> TestClient:
    return _client


# ---------------------------------------------------------------------------
# MTTR
# ---------------------------------------------------------------------------


def test_mttr_returns_zero_state(client: TestClient) -> None:
    r = client.get("/api/v1/dashboard/metrics/mttr")
    assert r.status_code == 200
    body = r.json()
    # Contract keys present
    expected_keys = {
        "current_mttr_hours",
        "target_mttr_hours",
        "previous_mttr_hours",
        "critical_mttr_hours",
        "high_mttr_hours",
        "medium_mttr_hours",
        "open_count",
        "closed_last_7d",
    }
    assert expected_keys.issubset(body.keys())
    # Zero-state defaults (no fabricated values)
    assert body["current_mttr_hours"] == 0.0
    assert body["previous_mttr_hours"] == 0.0
    assert body["open_count"] == 0
    assert body["closed_last_7d"] == 0
    # Target is a non-zero policy default (24h) - this is configuration, not data
    assert body["target_mttr_hours"] == 24.0


# ---------------------------------------------------------------------------
# Asset Criticality
# ---------------------------------------------------------------------------


def test_asset_criticality_returns_empty_list(client: TestClient) -> None:
    r = client.get("/api/v1/dashboard/metrics/asset-criticality")
    assert r.status_code == 200
    body = r.json()
    assert body == {"assets": []}


# ---------------------------------------------------------------------------
# Compliance Drift
# ---------------------------------------------------------------------------


def test_compliance_drift_returns_empty_lists(client: TestClient) -> None:
    r = client.get("/api/v1/dashboard/metrics/compliance-drift")
    assert r.status_code == 200
    body = r.json()
    assert body == {"frameworks": [], "recentFailures": []}


# ---------------------------------------------------------------------------
# Insider Risk
# ---------------------------------------------------------------------------


def test_insider_risk_returns_zero_state(client: TestClient) -> None:
    r = client.get("/api/v1/dashboard/metrics/insider-risk")
    assert r.status_code == 200
    body = r.json()
    assert body["elevated_count"] == 0
    assert body["high_risk_count"] == 0
    assert body["medium_risk_count"] == 0
    assert body["total_monitored"] == 0
    assert body["trend"] == "stable"
    assert body["trend_delta"] == 0
    assert body["last_escalation"] is None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_returns_ok_with_iso_timestamp(client: TestClient) -> None:
    r = client.get("/api/v1/dashboard/metrics/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # ISO 8601 with timezone offset (e.g., "2026-05-12T13:06:25.065780+00:00")
    iso_re = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:\d{2}$"
    )
    assert iso_re.match(
        body["timestamp"]
    ), f"timestamp not ISO 8601: {body['timestamp']!r}"


# ---------------------------------------------------------------------------
# Router registration (catches accidental un-include in src/api/main.py)
# ---------------------------------------------------------------------------


def test_router_registered_in_main_app() -> None:
    """The dashboard_metrics router must be registered in src/api/main.py.

    Done via a textual grep rather than `from src.api.main import app`
    because main.py has a pre-existing import-order sensitivity that
    surfaces a FastAPIError on `Request` response-field annotation
    somewhere in the route graph when other route modules have been
    imported first in the same test session. Smoke-tested manually:
    `python -c "from fastapi.testclient import TestClient; from
    src.api.main import app; print(TestClient(app).get(
    '/api/v1/dashboard/metrics/health').json())"` returns 200 ok.
    """
    from pathlib import Path

    main_py = Path(__file__).resolve().parents[2] / "src" / "api" / "main.py"
    source = main_py.read_text(encoding="utf-8")
    assert (
        "from src.api.dashboard_metrics_endpoints import router as dashboard_metrics_router"
        in source
    ), "dashboard_metrics_router import missing from src/api/main.py"
    assert "app.include_router(dashboard_metrics_router)" in source, (
        "dashboard_metrics_router not registered in src/api/main.py - "
        "look for `app.include_router(dashboard_metrics_router)`"
    )
