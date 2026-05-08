"""Integration tests for ADR-090 Phase 2 ingestion wiring.

Verifies that GitIngestionService routes parser-emitted relationships
through to NeptuneGraphService.add_relationship and that entities
receive canonical FQNs assigned by the per-job FQNBuilder.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship
from src.services.git_ingestion_service import GitIngestionService
from src.services.graph.edge_labels import EdgeLabel


@pytest.fixture
def mock_neptune():
    mock = MagicMock()
    mock.add_code_entity = MagicMock(return_value="entity-id")
    mock.add_relationship = MagicMock(return_value=True)
    mock.delete_outgoing_edges_for_file = MagicMock(return_value=0)
    return mock


@pytest.fixture
def mock_opensearch():
    mock = MagicMock()
    mock.index_embedding = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_embedding_service():
    mock = MagicMock()
    mock.generate_embedding = MagicMock(return_value=[0.1] * 1024)
    return mock


@pytest.fixture
def mock_observability():
    mock = MagicMock()
    mock.record_request = MagicMock()
    mock.record_latency = MagicMock()
    mock.record_success = MagicMock()
    mock.record_error = MagicMock()
    mock.record_resource_usage = MagicMock()
    mock.record_queue_depth = MagicMock()
    return mock


@pytest.fixture
def mock_ast_parser():
    """Parser mock that emits Phase 2 entities and relationships."""
    mock = MagicMock()
    mock.parse_file_with_relationships = MagicMock(
        return_value=(
            [
                CodeEntity(
                    name="App",
                    entity_type="class",
                    file_path="src/app.py",
                    line_number=1,
                ),
                CodeEntity(
                    name="run",
                    entity_type="method",
                    file_path="src/app.py",
                    line_number=5,
                    parent_entity="App",
                    parent_chain=("App",),
                ),
            ],
            [
                CodeRelationship(
                    source_name="App",
                    source_parent_chain=(),
                    target_name="Base",
                    relationship=EdgeLabel.INHERITS.value,
                    properties={"kind": "extends", "line": 1},
                ),
                CodeRelationship(
                    source_name="run",
                    source_parent_chain=("App",),
                    target_name="logger.info",
                    relationship=EdgeLabel.CALLS.value,
                    properties={"call_site_line": 6},
                ),
            ],
        )
    )
    return mock


@pytest.fixture
def service(
    mock_neptune,
    mock_opensearch,
    mock_embedding_service,
    mock_ast_parser,
    mock_observability,
):
    with tempfile.TemporaryDirectory() as temp_dir:
        yield GitIngestionService(
            neptune_service=mock_neptune,
            opensearch_service=mock_opensearch,
            embedding_service=mock_embedding_service,
            ast_parser=mock_ast_parser,
            observability_service=mock_observability,
            clone_base_path=temp_dir,
        )


class TestRelationshipPropagation:
    @pytest.mark.asyncio
    async def test_populate_graph_writes_relationships(
        self, service, mock_neptune, mock_ast_parser
    ):
        entities = [
            CodeEntity(name="A", entity_type="class", file_path="a.py", line_number=1),
        ]
        relationships = [
            CodeRelationship(
                source_name="A",
                source_parent_chain=(),
                target_name="B",
                relationship=EdgeLabel.INHERITS.value,
                properties={"kind": "extends"},
            ),
            CodeRelationship(
                source_name="A",
                source_parent_chain=(),
                target_name="something",
                relationship=EdgeLabel.CALLS.value,
                properties={"call_site_line": 3},
            ),
        ]

        await service._populate_graph(
            entities,
            "https://github.com/o/r",
            "main",
            relationships=relationships,
        )

        # Both new edges land in add_relationship via keyword args.
        labels_written = [
            call.kwargs.get("relationship")
            or (call.args[2] if len(call.args) >= 3 else None)
            for call in mock_neptune.add_relationship.call_args_list
        ]
        assert EdgeLabel.INHERITS.value in labels_written
        assert EdgeLabel.CALLS.value in labels_written

    @pytest.mark.asyncio
    async def test_no_relationships_does_not_call_add_relationship_for_phase2(
        self, service, mock_neptune
    ):
        """Legacy structural edges (CONTAINS, DEPENDS_ON) still flow."""
        entities = [
            CodeEntity(
                name="A",
                entity_type="class",
                file_path="a.py",
                line_number=1,
                dependencies=["BaseA"],
            )
        ]
        await service._populate_graph(entities, "https://github.com/o/r", "main")
        # The legacy DEPENDS_ON path still fires; we just don't emit
        # the Phase 2 edges in the absence of a parser-emitted list.
        called_labels = [
            (
                call.kwargs.get("relationship")
                or (call.args[2] if len(call.args) > 2 else None)
            )
            for call in mock_neptune.add_relationship.call_args_list
        ]
        assert EdgeLabel.CALLS.value not in called_labels
        assert EdgeLabel.INHERITS.value not in called_labels


class TestFQNAssignment:
    @pytest.mark.asyncio
    async def test_entity_receives_fqn_metadata(self, service, mock_neptune):
        entities = [
            CodeEntity(
                name="App",
                entity_type="class",
                file_path="src/app.py",
                line_number=1,
            ),
            CodeEntity(
                name="run",
                entity_type="method",
                file_path="src/app.py",
                line_number=5,
                parent_entity="App",
                parent_chain=("App",),
            ),
        ]

        await service._populate_graph(entities, "https://github.com/owner/repo", "main")

        fqns_passed = [
            call.kwargs.get("metadata", {}).get("fqn")
            for call in mock_neptune.add_code_entity.call_args_list
        ]
        # Both entities got an FQN; method's includes the parent chain.
        assert any(fqn and fqn.endswith("App#class") for fqn in fqns_passed)
        assert any(fqn and fqn.endswith("App.run#method") for fqn in fqns_passed)

    @pytest.mark.asyncio
    async def test_overload_methods_get_disambiguated_fqns(self, service, mock_neptune):
        entities = [
            CodeEntity(
                name="get",
                entity_type="method",
                file_path="src/api.py",
                line_number=1,
                parent_chain=("Router",),
            ),
            CodeEntity(
                name="get",
                entity_type="method",
                file_path="src/api.py",
                line_number=2,
                parent_chain=("Router",),
            ),
            CodeEntity(
                name="get",
                entity_type="method",
                file_path="src/api.py",
                line_number=3,
                parent_chain=("Router",),
            ),
        ]
        await service._populate_graph(entities, "https://github.com/owner/repo", "main")

        fqns = [
            call.kwargs.get("metadata", {}).get("fqn")
            for call in mock_neptune.add_code_entity.call_args_list
        ]
        # First emission: no suffix. Second: @1. Third: @2.
        assert any(fqn and fqn.endswith("Router.get#method") for fqn in fqns)
        assert any(fqn and fqn.endswith("@1") for fqn in fqns)
        assert any(fqn and fqn.endswith("@2") for fqn in fqns)


class TestParserOutputThreading:
    @pytest.mark.asyncio
    async def test_parse_files_with_relationships_returns_both(
        self, service, mock_ast_parser, tmp_path
    ):
        py_file = tmp_path / "x.py"
        py_file.write_text("class X: pass\n")
        entities, relationships = await service._parse_files_with_relationships(
            [py_file], tmp_path
        )
        # Mock parser returns 2 entities + 2 relationships per call.
        assert len(entities) == 2
        assert len(relationships) == 2

    @pytest.mark.asyncio
    async def test_parse_files_legacy_signature_still_returns_entities(
        self, service, mock_ast_parser, tmp_path
    ):
        py_file = tmp_path / "x.py"
        py_file.write_text("class X: pass\n")
        result = await service._parse_files([py_file], tmp_path)
        # Legacy callers still get a flat entity list.
        assert isinstance(result, list)
        assert len(result) == 2
