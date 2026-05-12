"""Tests for ``src/api/system_health_endpoints.py`` (#182 Wave 9).

Stub endpoint that backs the HealthCheckModal. Returns honest
unknown/zero-state body until real per-service probes land.
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.system_health_endpoints import router

_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app)


@pytest.fixture
def client() -> TestClient:
    return _client


def test_system_health_returns_unknown_zero_state(client: TestClient) -> None:
    r = client.get("/api/v1/system-health")
    assert r.status_code == 200
    body = r.json()
    assert body["overallStatus"] == "unknown"
    assert body["healthyServices"] == 0
    assert body["degradedServices"] == 0
    assert body["unhealthyServices"] == 0
    assert body["categories"] == {}
    # Summary is non-empty - tells the operator the probes aren't enabled
    assert body["summary"]
    # lastUpdated is ISO 8601
    iso_re = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:\d{2}$"
    )
    assert iso_re.match(
        body["lastUpdated"]
    ), f"lastUpdated not ISO 8601: {body['lastUpdated']!r}"


def test_router_registered_in_main_app() -> None:
    """Verify the router is wired into src/api/main.py.

    Textual check rather than `from src.api.main import app` because
    main.py has a pre-existing import-order sensitivity (#163 Wave 8).
    """
    from pathlib import Path

    main_py = Path(__file__).resolve().parents[2] / "src" / "api" / "main.py"
    source = main_py.read_text(encoding="utf-8")
    assert (
        "from src.api.system_health_endpoints import router as system_health_router"
        in source
    )
    assert "app.include_router(system_health_router)" in source
