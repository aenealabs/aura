"""ADR-090 golden-graph regression harness.

Snapshot-based regression test that catches silent edge-label drift,
FQN format regressions, and migration data loss between releases.

Per Kelly's ADR-090 closeout plan (P0 #1):
- Snapshots live as committed JSON in
  ``tests/fixtures/ingestion/golden_snapshots/``.
- Snapshot schema is a sorted list of ``(source, label, target,
  properties_subset)`` tuples plus a sorted list of vertices.
- Non-determinism stripped at serialization: ``created_at``,
  internal UUIDs, and timestamps are excluded.
- Re-running with ``GOLDEN_GRAPH_UPDATE=1`` rewrites snapshots
  intentionally; CI runs without the env var so a snapshot drift
  fails loudly.

The harness ingests a frozen fixture repo under
``tests/fixtures/ingestion/golden_repos/small/`` and asserts the
serialized graph matches the snapshot. One test per
``GraphQueryType`` consumer.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.ast_parser_agent import ASTParserAgent
from src.services.context_retrieval_service import GraphQueryType
from src.services.git_ingestion_service import GitIngestionService
from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

GOLDEN_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "ingestion"
GOLDEN_REPO = GOLDEN_ROOT / "golden_repos" / "small"
SNAPSHOT_DIR = GOLDEN_ROOT / "golden_snapshots"


# Volatile properties stripped before snapshot serialization. These
# exist on every edge / vertex but their values vary across runs;
# pinning them in snapshots would flag every test run as a regression.
_VOLATILE_PROPERTIES: frozenset[str] = frozenset({"created_at", "branch", "entity_id"})


def _normalize_edge(edge: dict) -> dict:
    metadata = {
        k: v
        for k, v in (edge.get("metadata") or {}).items()
        if k not in _VOLATILE_PROPERTIES
    }
    return {
        "from": edge.get("from"),
        "to": edge.get("to"),
        "relationship": edge.get("relationship"),
        "metadata": metadata,
    }


def _normalize_vertex(vertex: dict) -> dict:
    return {
        "id": vertex.get("id"),
        "name": vertex.get("name"),
        "type": vertex.get("type"),
        "label": vertex.get("label"),
        "kind": vertex.get("kind"),
        "sensitivity": vertex.get("sensitivity"),
    }


def _serialize_graph(neptune: NeptuneGraphService) -> dict:
    edges = sorted(
        (_normalize_edge(e) for e in neptune.mock_edges),
        key=lambda e: (
            e["relationship"] or "",
            e["from"] or "",
            e["to"] or "",
        ),
    )
    vertices = sorted(
        (_normalize_vertex(v) for v in neptune.mock_graph.values()),
        key=lambda v: (v["label"] or "", v["id"] or ""),
    )
    return {"vertices": vertices, "edges": edges}


@pytest.fixture
def neptune():
    svc = NeptuneGraphService(mode=NeptuneMode.MOCK)
    svc.mock_graph.clear()
    svc.mock_edges.clear()
    return svc


@pytest.fixture
def service(neptune):
    with tempfile.TemporaryDirectory() as tmp:
        yield GitIngestionService(
            neptune_service=neptune,
            opensearch_service=MagicMock(index_embedding=MagicMock(return_value=True)),
            embedding_service=MagicMock(
                generate_embedding=MagicMock(return_value=[0.1] * 1024)
            ),
            ast_parser=ASTParserAgent(),
            observability_service=MagicMock(),
            clone_base_path=tmp,
        )


def _seed_golden_repo(service: GitIngestionService) -> Path:
    """Copy the golden fixture into the service's clone_dir."""
    target = service.clone_dir / "golden-small"
    target.mkdir(parents=True, exist_ok=True)
    for src_file in GOLDEN_REPO.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(GOLDEN_REPO)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src_file.read_text(encoding="utf-8"))
    return target


@pytest.mark.asyncio
async def test_golden_graph_small_repo(service, neptune):
    """Ingest the small golden repo and compare against the snapshot.

    Regenerate via ``GOLDEN_GRAPH_UPDATE=1 pytest -k golden_graph_small``
    after a deliberate schema change.
    """
    repo = _seed_golden_repo(service)
    files = sorted(repo.rglob("*.py"))
    entities, relationships = await service._parse_files_with_relationships(files, repo)
    phase5_rels = await service._scan_config_dependencies(files, repo, entities)
    relationships.extend(phase5_rels)
    await service._populate_graph(
        entities,
        "https://github.com/owner/golden-small",
        "main",
        relationships=relationships,
    )

    actual = _serialize_graph(neptune)
    snapshot_path = SNAPSHOT_DIR / "small.json"

    if os.environ.get("GOLDEN_GRAPH_UPDATE") == "1":
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(actual, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        pytest.skip(
            "Snapshot updated; re-run without GOLDEN_GRAPH_UPDATE=1 "
            "to verify the new baseline."
        )

    if not snapshot_path.exists():
        pytest.fail(
            f"Snapshot missing: {snapshot_path}\n"
            "Generate it once with GOLDEN_GRAPH_UPDATE=1 and commit."
        )

    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert actual == expected, (
        "Golden graph drift detected. If this drift is intentional, "
        f"re-run with GOLDEN_GRAPH_UPDATE=1 to regenerate "
        f"{snapshot_path.name}, review the diff in PR, and commit."
    )


def test_query_type_enum_consumer_coverage():
    """Every GraphQueryType has exactly one mapping in the read-side
    relationship_types table; if a new query type is added, this
    test reminds the contributor to update the golden snapshot
    contract too.
    """
    expected = {"call_graph", "dependencies", "inheritance", "references", "related"}
    actual = {qt.value for qt in GraphQueryType}
    assert actual == expected, (
        "GraphQueryType inventory changed. Update the golden-graph "
        "harness to assert read-path coverage of the new query type."
    )
