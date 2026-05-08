"""Phase 5.2 integration tests: ConfigDependencyAgent ingestion wiring.

Verifies that the Phase 5 config-dependency stage runs in
GitIngestionService, materializes ConfigParameter / KMSAlias /
FeatureFlag vertices, and writes Phase 5 edges with the right
sensitivity properties.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.services.git_ingestion_service import GitIngestionService
from src.services.graph.config_dependency_agent import (
    SENSITIVITY_CONFIDENTIAL,
    SENSITIVITY_RESTRICTED,
    VERTEX_CONFIG_PARAMETER,
    VERTEX_FEATURE_FLAG,
    VERTEX_KMS_ALIAS,
)
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
    """Real ASTParserAgent + real ConfigDependencyAgent with a mock
    Neptune. Exercises the full ingestion pipeline end-to-end on a
    tiny in-memory repo."""
    from src.agents.ast_parser_agent import ASTParserAgent

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


def _make_repo(service: GitIngestionService, contents: str) -> Path:
    """Create a fixture repo inside the service's clone_dir.

    Reusing clone_dir keeps the path-traversal guard in
    _read_file_content satisfied (it rejects files outside the
    expected clone tree as a defense against malicious symlinks).
    """
    repo = service.clone_dir / "phase5-fixture"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "app.py").write_text(contents)
    return repo


# -- Phase 5 vertex writers --------------------------------------------


class TestPhase5VertexWriters:
    def test_add_config_parameter_vertex(self, neptune):
        vid = neptune.add_config_parameter(name="/myapp/db/password", kind="ssm")
        assert vid == "/myapp/db/password"
        record = neptune.mock_graph[vid]
        assert record["label"] == "ConfigParameter"
        assert record["kind"] == "ssm"
        assert record["sensitivity"] == "restricted"

    def test_add_kms_alias_vertex(self, neptune):
        vid = neptune.add_kms_alias(alias="alias/myapp")
        record = neptune.mock_graph[vid]
        assert record["label"] == "KMSAlias"
        assert record["sensitivity"] == "restricted"

    def test_add_feature_flag_vertex_default_confidential(self, neptune):
        vid = neptune.add_feature_flag(flag_name="checkout-v2")
        record = neptune.mock_graph[vid]
        assert record["label"] == "FeatureFlag"
        assert record["sensitivity"] == "confidential"


# -- End-to-end ingestion ----------------------------------------------


class TestPhase5Ingestion:
    @pytest.mark.asyncio
    async def test_phase5_edges_and_vertices_land_in_graph(self, service, neptune):
        repo = _make_repo(
            service,
            "import os\n"
            "import boto3\n"
            "def boot():\n"
            "    db = os.environ.get('DATABASE_URL')\n"
            "    p = ssm.get_parameter(Name='/myapp/conf/key')\n"
            "    k = kms.decrypt(KeyId='alias/myapp')\n"
            "    flag = ldclient.variation('new-checkout', user, False)\n"
            "    return (db, p, k, flag)\n",
        )

        entities, relationships = await service._parse_files_with_relationships(
            [repo / "app.py"], repo
        )
        phase5_rels = await service._scan_config_dependencies(
            [repo / "app.py"], repo, entities
        )
        relationships.extend(phase5_rels)

        await service._populate_graph(
            entities,
            "https://github.com/owner/repo",
            "main",
            relationships=relationships,
        )

        edge_labels = {e["relationship"] for e in neptune.mock_edges}
        assert EdgeLabel.DEPENDS_ON_ENV.value in edge_labels
        assert EdgeLabel.READS_CONFIG.value in edge_labels
        assert EdgeLabel.USES_KMS_KEY.value in edge_labels
        assert EdgeLabel.FEATURE_GATED_BY.value in edge_labels

        labels_by_id = {
            v["id"]: v["label"]
            for v in neptune.mock_graph.values()
            if v.get("label")
            in {VERTEX_CONFIG_PARAMETER, VERTEX_KMS_ALIAS, VERTEX_FEATURE_FLAG}
        }
        assert labels_by_id["DATABASE_URL"] == VERTEX_CONFIG_PARAMETER
        assert labels_by_id["/myapp/conf/key"] == VERTEX_CONFIG_PARAMETER
        assert labels_by_id["alias/myapp"] == VERTEX_KMS_ALIAS
        assert labels_by_id["new-checkout"] == VERTEX_FEATURE_FLAG

    @pytest.mark.asyncio
    async def test_phase5_edges_carry_sensitivity_metadata(self, service, neptune):
        repo = _make_repo(
            service,
            "import os\n"
            "def go():\n"
            "    return os.environ.get('THING'), kms.decrypt(KeyId='alias/x')\n",
        )
        entities, relationships = await service._parse_files_with_relationships(
            [repo / "app.py"], repo
        )
        phase5_rels = await service._scan_config_dependencies(
            [repo / "app.py"], repo, entities
        )
        relationships.extend(phase5_rels)
        await service._populate_graph(
            entities,
            "https://github.com/owner/repo",
            "main",
            relationships=relationships,
        )

        env_edges = [
            e
            for e in neptune.mock_edges
            if e["relationship"] == EdgeLabel.DEPENDS_ON_ENV.value
        ]
        kms_edges = [
            e
            for e in neptune.mock_edges
            if e["relationship"] == EdgeLabel.USES_KMS_KEY.value
        ]
        assert env_edges
        assert kms_edges
        assert env_edges[0]["metadata"]["sensitivity"] == SENSITIVITY_CONFIDENTIAL
        assert kms_edges[0]["metadata"]["sensitivity"] == SENSITIVITY_RESTRICTED

    @pytest.mark.asyncio
    async def test_phase5_vertex_dedupes_across_call_sites(self, service, neptune):
        repo = _make_repo(
            service,
            "import os\n"
            "def a():\n"
            "    return os.environ.get('SHARED')\n"
            "def b():\n"
            "    return os.environ.get('SHARED')\n",
        )
        entities, relationships = await service._parse_files_with_relationships(
            [repo / "app.py"], repo
        )
        phase5_rels = await service._scan_config_dependencies(
            [repo / "app.py"], repo, entities
        )
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
            if v.get("name") == "SHARED" and v.get("label") == VERTEX_CONFIG_PARAMETER
        ]
        assert len(shared_vertices) == 1
        edges_to_shared = [
            e
            for e in neptune.mock_edges
            if e["to"] == "SHARED"
            and e["relationship"] == EdgeLabel.DEPENDS_ON_ENV.value
        ]
        assert len(edges_to_shared) == 2
