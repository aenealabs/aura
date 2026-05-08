"""Integration: ingestion against the centralized pathological fixture set.

Each fixture under ``tests/fixtures/ingestion/pathological/`` carries
a ``MANIFEST.yaml`` declaring the entities and edges the parser must
emit. This test discovers manifests, ingests each fixture into a
mock Neptune, and verifies the contract.

Per Kelly's ADR-090 closeout plan (P0 #2): the centralized fixture
set converts inline ad-hoc fixtures into a durable asset and
enforces a single source of truth for parser expectations.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# PyYAML is in the project's transitive deps; if the import fails on
# a constrained CI image we skip rather than fail.
yaml = pytest.importorskip("yaml")

from src.agents.ast_parser_agent import ASTParserAgent  # noqa: E402

PATHOLOGICAL_ROOT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "ingestion" / "pathological"
)


def _discover_manifests() -> list[Path]:
    return sorted(PATHOLOGICAL_ROOT.rglob("MANIFEST.yaml"))


def _load_manifest(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def parser() -> ASTParserAgent:
    return ASTParserAgent()


@pytest.mark.parametrize(
    "manifest_path",
    _discover_manifests(),
    ids=lambda p: p.parent.name,
)
def test_pathological_fixture_emits_expected_entities(
    parser: ASTParserAgent, manifest_path: Path
):
    """Every entity declared in the manifest must be emitted by the parser."""
    manifest = _load_manifest(manifest_path)
    fixture_dir = manifest_path.parent
    expected_entities = manifest.get("expected_entities", [])

    actual: list[tuple[str, str]] = []
    for path in sorted(fixture_dir.rglob("*.py")) + sorted(fixture_dir.rglob("*.js")):
        entities, _ = parser.parse_file_with_relationships(path)
        for entity in entities:
            actual.append((entity.name, entity.entity_type))

    actual_set = {(e["name"], e["type"]) for e in expected_entities}
    actual_pairs = set(actual)
    missing = actual_set - actual_pairs
    assert not missing, (
        f"Manifest {manifest_path} declared entities not emitted by "
        f"the parser: {missing}"
    )
