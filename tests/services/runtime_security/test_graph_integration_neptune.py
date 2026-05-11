"""Tests for Wave 5a Neptune writes in ``runtime_security.graph_integration``.

Replaces the two ``NotImplementedError`` sites in ``_store_vertex`` /
``_create_edge`` with real Gremlin upserts via an injected Neptune
client. These tests verify both modes:

  - Mock mode unchanged: writes go to ``_mock_vertices`` /
    ``_mock_edges``.
  - Live mode with an injected client: writes produce well-formed
    Gremlin queries and call ``client.submit().all().result()``.
  - Defensive: ``use_mock=False`` AND ``neptune_client=None`` falls
    back to the mock dict rather than raising.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.services.runtime_security.config import (
    GraphIntegrationConfig,
    RuntimeSecurityConfig,
)
from src.services.runtime_security.graph_integration import (
    EdgeLabel,
    GraphVertex,
    RuntimeSecurityGraphService,
    VertexLabel,
    escape_gremlin_string,
)


def _live_config() -> RuntimeSecurityConfig:
    return RuntimeSecurityConfig(graph=GraphIntegrationConfig(use_mock=False))


def _ok_client() -> MagicMock:
    client = MagicMock()
    client.submit.return_value.all.return_value.result.return_value = []
    return client


# ---------------------------------------------------------------------------
# Mock-mode preservation
# ---------------------------------------------------------------------------


def test_default_mode_is_mock_and_uses_in_memory_dict() -> None:
    svc = RuntimeSecurityGraphService()

    assert svc._use_mock is True
    svc._store_vertex(GraphVertex(vertex_id="v1", label=VertexLabel.RUNTIME_EVENT))

    assert "v1" in svc._mock_vertices


def test_live_config_but_no_client_falls_back_to_mock() -> None:
    """Defensive: prevents a misconfigured wiring from raising in prod."""
    svc = RuntimeSecurityGraphService(config=_live_config())  # no client

    # config requests live mode, but absence of client forces mock
    assert svc._use_mock is True


# ---------------------------------------------------------------------------
# Live mode - vertex writes
# ---------------------------------------------------------------------------


def test_store_vertex_submits_upsert_gremlin_query() -> None:
    client = _ok_client()
    svc = RuntimeSecurityGraphService(config=_live_config(), neptune_client=client)
    assert svc._use_mock is False

    vertex = GraphVertex(
        vertex_id="event-1",
        label=VertexLabel.RUNTIME_EVENT,
        properties={"severity": "HIGH", "event_type": "ESCAPE"},
    )

    svc._store_vertex(vertex)

    assert client.submit.call_count == 1
    query = client.submit.call_args[0][0]

    # Idempotent upsert pattern
    assert "g.V().has('RuntimeEvent', 'vertex_id', 'event-1')" in query
    assert ".fold()" in query
    assert ".coalesce(unfold()" in query
    assert "addV('RuntimeEvent').property(id, 'event-1')" in query
    # Per-property writes
    assert "property(single, 'severity', 'HIGH')" in query
    assert "property(single, 'event_type', 'ESCAPE')" in query


def test_store_vertex_escapes_special_chars_in_id_and_props() -> None:
    client = _ok_client()
    svc = RuntimeSecurityGraphService(config=_live_config(), neptune_client=client)

    vertex = GraphVertex(
        vertex_id="evt'1",
        label=VertexLabel.RUNTIME_EVENT,
        properties={"msg": "it's a test\nsecond line"},
    )

    svc._store_vertex(vertex)

    query = client.submit.call_args[0][0]
    # Single quotes inside identifiers + values must be backslash-escaped
    assert "evt\\'1" in query
    assert "it\\'s a test\\nsecond line" in query


def test_store_vertex_propagates_neptune_failure() -> None:
    client = MagicMock()
    client.submit.return_value.all.return_value.result.side_effect = RuntimeError(
        "Neptune 5xx"
    )
    svc = RuntimeSecurityGraphService(config=_live_config(), neptune_client=client)

    with pytest.raises(RuntimeError, match="Neptune 5xx"):
        svc._store_vertex(GraphVertex(vertex_id="v", label=VertexLabel.RUNTIME_EVENT))


# ---------------------------------------------------------------------------
# Live mode - edge writes
# ---------------------------------------------------------------------------


def test_create_edge_submits_addE_gremlin_query() -> None:
    client = _ok_client()
    svc = RuntimeSecurityGraphService(config=_live_config(), neptune_client=client)

    edge_id = svc._create_edge(
        EdgeLabel.TRIGGERED_BY,
        "event-1",
        "image-2",
        properties={"confidence": "high"},
    )

    assert isinstance(edge_id, str) and edge_id.startswith("edge-")
    assert client.submit.call_count == 1
    query = client.submit.call_args[0][0]

    assert "g.V().has('vertex_id', 'event-1').as('a')" in query
    assert "V().has('vertex_id', 'image-2').as('b')" in query
    assert "addE('TRIGGERED_BY').from('a').to('b')" in query
    assert f"property(id, '{edge_id}')" in query
    assert "property('confidence', 'high')" in query


def test_create_edge_returns_unique_ids_per_call() -> None:
    client = _ok_client()
    svc = RuntimeSecurityGraphService(config=_live_config(), neptune_client=client)

    e1 = svc._create_edge(EdgeLabel.TRIGGERED_BY, "a", "b")
    e2 = svc._create_edge(EdgeLabel.TRIGGERED_BY, "a", "b")

    assert e1 != e2


def test_create_edge_propagates_neptune_failure() -> None:
    client = MagicMock()
    client.submit.return_value.all.return_value.result.side_effect = RuntimeError(
        "Neptune 4xx"
    )
    svc = RuntimeSecurityGraphService(config=_live_config(), neptune_client=client)

    with pytest.raises(RuntimeError, match="Neptune 4xx"):
        svc._create_edge(EdgeLabel.TRIGGERED_BY, "a", "b")


# ---------------------------------------------------------------------------
# Gremlin escape helper
# ---------------------------------------------------------------------------


def test_escape_gremlin_string_handles_special_chars() -> None:
    assert escape_gremlin_string("it's") == "it\\'s"
    assert escape_gremlin_string("a\\b") == "a\\\\b"
    assert escape_gremlin_string("line1\nline2") == "line1\\nline2"
    assert escape_gremlin_string("") == ""


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------


def test_close_clears_client_reference() -> None:
    client = _ok_client()
    svc = RuntimeSecurityGraphService(config=_live_config(), neptune_client=client)

    svc.close()

    assert svc._neptune_client is None
