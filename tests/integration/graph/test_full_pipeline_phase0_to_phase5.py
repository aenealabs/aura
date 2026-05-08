"""Cross-phase integration: full ADR-090 pipeline end-to-end.

Drives a representative repo through GitIngestionService with real
parsers (Phase 2/3), real Tier 1+2 resolvers (Tier 3 stubbed), the
real ConfigDependencyAgent, and a Neptune mock that records every
write. Asserts that the recorded edge set matches what each phase
of the ADR is supposed to produce.

Per Kelly's ADR-090 closeout plan (P0 #4): real parsers + mock
Neptune is the right balance -- parsers are deterministic and worth
exercising, Neptune wire I/O is not. Tier 3 LLM is stubbed because
its behaviour is exhaustively tested in the dedicated Phase 4c
suites; here we only assert that the resolver chain wires up
correctly.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.ast_parser_agent import ASTParserAgent
from src.services.git_ingestion_service import GitIngestionService
from src.services.graph.edge_labels import EdgeLabel
from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode


@pytest.fixture
def neptune():
    svc = NeptuneGraphService(mode=NeptuneMode.MOCK)
    svc.mock_graph.clear()
    svc.mock_edges.clear()
    return svc


@pytest.fixture
def service(neptune):
    """Real parsers + real config agent; mock Neptune; no Bedrock."""
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


def _seed_repo(service: GitIngestionService, files: dict[str, str]) -> Path:
    repo = service.clone_dir / "fullpipe-fixture"
    repo.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return repo


@pytest.mark.asyncio
async def test_full_pipeline_emits_expected_edge_set(service, neptune):
    """The full ADR-090 pipeline produces the expected edge inventory.

    Fixture covers every phase deliberately:
      - Phase 2: function, method, class, CALLS, INHERITS, IMPORTS
      - Phase 4a: cross-file CALLS via direct import
      - Phase 4b: self-method resolution + inherited method
      - Phase 5: env var, SSM, KMS alias, feature flag
    """
    repo = _seed_repo(
        service,
        {
            "myapp/utils.py": ("def helper():\n    return 1\n"),
            "myapp/api.py": (
                "import os\n"
                "from myapp.utils import helper\n"
                "import boto3\n\n"
                "class Base:\n"
                "    def shared(self):\n"
                "        return 0\n\n"
                "class Handler(Base):\n"
                "    def handle(self):\n"
                "        # Phase 4a: direct-import resolution.\n"
                "        helper()\n"
                "        # Phase 4b: self-method via inheritance.\n"
                "        self.shared()\n"
                "        # Phase 5: env var + SSM + KMS + flag.\n"
                "        os.environ.get('DATABASE_URL')\n"
                "        ssm.get_parameter(Name='/myapp/conf/k')\n"
                "        kms.decrypt(KeyId='alias/myapp')\n"
                "        ldclient.variation('checkout-v2', user, False)\n"
            ),
        },
    )

    files = [repo / "myapp/utils.py", repo / "myapp/api.py"]
    entities, relationships = await service._parse_files_with_relationships(files, repo)
    phase5_rels = await service._scan_config_dependencies(files, repo, entities)
    relationships.extend(phase5_rels)
    await service._populate_graph(
        entities,
        "https://github.com/owner/repo",
        "main",
        relationships=relationships,
    )

    edge_labels = {e["relationship"] for e in neptune.mock_edges}

    # Phase 2/3 structural edges.
    assert EdgeLabel.CALLS.value in edge_labels
    assert EdgeLabel.INHERITS.value in edge_labels
    assert EdgeLabel.IMPORTS.value in edge_labels

    # Phase 5 config edges.
    assert EdgeLabel.DEPENDS_ON_ENV.value in edge_labels
    assert EdgeLabel.READS_CONFIG.value in edge_labels
    assert EdgeLabel.USES_KMS_KEY.value in edge_labels
    assert EdgeLabel.FEATURE_GATED_BY.value in edge_labels


@pytest.mark.asyncio
async def test_tier1_resolves_direct_import_to_canonical_fqn(service, neptune):
    """Phase 4a resolution lands on the canonical FQN at edge endpoint."""
    repo = _seed_repo(
        service,
        {
            "myapp/utils.py": "def helper():\n    return 1\n",
            "myapp/runner.py": (
                "from myapp.utils import helper\n" "def main():\n    helper()\n"
            ),
        },
    )

    files = [repo / "myapp/utils.py", repo / "myapp/runner.py"]
    entities, relationships = await service._parse_files_with_relationships(files, repo)
    await service._populate_graph(
        entities,
        "https://github.com/owner/repo",
        "main",
        relationships=relationships,
    )

    # The CALLS edge from main to helper should land with a Phase 1
    # canonical FQN as ``to_entity``, not the raw name ``helper``.
    # Tier 1's same-file lookup may resolve to the import-statement
    # entity rather than the cross-file definition; either form is a
    # canonical FQN and either satisfies the resolution contract.
    call_edges = [
        e
        for e in neptune.mock_edges
        if e["relationship"] == EdgeLabel.CALLS.value
        and e.get("metadata", {}).get("call_site_line") is not None
    ]
    assert call_edges
    fqn_targets = [
        e["to"]
        for e in call_edges
        if e["to"].startswith("python:") and ":helper#" in e["to"]
    ]
    assert fqn_targets, (
        "Tier 1 did not resolve the call to a canonical FQN. "
        f"Edges seen: {[e['to'] for e in call_edges]}"
    )


@pytest.mark.asyncio
async def test_phase5_vertices_dedupe_across_files(service, neptune):
    """Same env var referenced from two files materializes one vertex."""
    repo = _seed_repo(
        service,
        {
            "myapp/a.py": (
                "import os\n" "def fa():\n" "    return os.environ.get('SHARED_VAR')\n"
            ),
            "myapp/b.py": (
                "import os\n" "def fb():\n" "    return os.environ.get('SHARED_VAR')\n"
            ),
        },
    )

    files = [repo / "myapp/a.py", repo / "myapp/b.py"]
    entities, relationships = await service._parse_files_with_relationships(files, repo)
    phase5_rels = await service._scan_config_dependencies(files, repo, entities)
    relationships.extend(phase5_rels)
    await service._populate_graph(
        entities,
        "https://github.com/owner/repo",
        "main",
        relationships=relationships,
    )

    shared_vertices = [
        v
        for v in neptune.mock_graph.values()
        if v.get("name") == "SHARED_VAR" and v.get("label") == "ConfigParameter"
    ]
    assert len(shared_vertices) == 1
    edges_to_shared = [
        e
        for e in neptune.mock_edges
        if e["to"] == "SHARED_VAR"
        and e["relationship"] == EdgeLabel.DEPENDS_ON_ENV.value
    ]
    assert len(edges_to_shared) == 2
