"""
Project Aura - Service Adapters Tests

Tests for the adapter classes that wrap real AWS services (Neptune, OpenSearch)
with the same interface as mock implementations.

Target: 85% coverage of src/services/service_adapters.py
"""

import os
from unittest.mock import MagicMock, patch

# Set environment before importing
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

from src.services.service_adapters import (
    NeptuneGraphAdapter,
    OpenSearchVectorAdapter,
    create_graph_agent,
    create_vector_store,
)


class TestNeptuneGraphAdapterInit:
    """Tests for NeptuneGraphAdapter initialization."""

    def test_init_with_neptune_service(self):
        """Test initialization with Neptune service."""
        mock_neptune = MagicMock()

        adapter = NeptuneGraphAdapter(mock_neptune)

        assert adapter.neptune == mock_neptune
        assert isinstance(adapter.ckge_graph, dict)
        assert len(adapter.ckge_graph) == 0


class TestNeptuneGraphAdapterParseSourceCode:
    """Tests for parse_source_code method."""

    def test_parse_source_code_with_content(self):
        """Test parsing source code from content string."""
        mock_neptune = MagicMock()
        mock_neptune.add_code_entity.return_value = "entity-001"

        adapter = NeptuneGraphAdapter(mock_neptune)

        code_content = """
class TestClass:
    def test_method(self):
        pass
"""

        with patch("src.agents.ast_parser_agent.ASTParserAgent") as mock_parser_class:
            mock_parser = MagicMock()
            mock_entity = MagicMock()
            mock_entity.name = "TestClass"
            mock_entity.entity_type = "class"
            mock_entity.line_number = 2
            mock_parser.parse_file.return_value = [mock_entity]
            mock_parser_class.return_value = mock_parser

            result = adapter.parse_source_code(code_content, "test.py")

            assert "file" in result
            assert "classes" in result
            assert "dependencies" in result

    def test_parse_source_code_empty_entities(self):
        """Test parsing returns empty result for no entities."""
        mock_neptune = MagicMock()
        adapter = NeptuneGraphAdapter(mock_neptune)

        # Use real AST parser with empty file
        with patch("src.agents.ast_parser_agent.ASTParserAgent") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.parse_file.return_value = []
            mock_parser_class.return_value = mock_parser

            result = adapter.parse_source_code("# Empty file", "empty.py")

            assert result["classes"] == []
            assert result["dependencies"] == []

    def test_parse_source_code_with_function_entity(self):
        """Test parsing with function entity type - lines 145-148."""
        mock_neptune = MagicMock()
        mock_neptune.add_code_entity.return_value = "entity-001"

        adapter = NeptuneGraphAdapter(mock_neptune)

        with patch("src.agents.ast_parser_agent.ASTParserAgent") as mock_parser_class:
            mock_parser = MagicMock()
            # Create class entity first, then function entity
            class_entity = MagicMock()
            class_entity.name = "MyClass"
            class_entity.entity_type = "class"
            class_entity.line_number = 1

            func_entity = MagicMock()
            func_entity.name = "my_method"
            func_entity.entity_type = "function"
            func_entity.line_number = 2

            mock_parser.parse_file.return_value = [class_entity, func_entity]
            mock_parser_class.return_value = mock_parser

            result = adapter.parse_source_code(
                "class MyClass:\n    def my_method(self): pass", "test.py"
            )

            # Function should be added as method to last class
            assert len(result["classes"]) == 1
            assert "my_method" in result["classes"][0]["methods"]

    def test_parse_source_code_nonexistent_file(self):
        """Test parsing with non-existent file path - line 113."""
        mock_neptune = MagicMock()
        adapter = NeptuneGraphAdapter(mock_neptune)

        with patch("src.agents.ast_parser_agent.ASTParserAgent") as mock_parser_class:
            mock_parser = MagicMock()
            # Parser returns empty list when file doesn't exist
            mock_parser.parse_file.return_value = []
            mock_parser_class.return_value = mock_parser

            # Pass a non-existent file path (not content)
            result = adapter.parse_source_code(None, "/nonexistent/path/file.py")

            assert result["classes"] == []
            assert result["dependencies"] == []


class TestNeptuneGraphAdapterAddNode:
    """Tests for add_node method."""

    def test_add_node_basic(self):
        """Test adding a basic node."""
        mock_neptune = MagicMock()
        adapter = NeptuneGraphAdapter(mock_neptune)

        adapter.add_node("node-001", "CLASS", name="TestClass", file="test.py", line=10)

        mock_neptune.add_code_entity.assert_called_once()
        assert "node-001" in adapter.ckge_graph
        assert adapter.ckge_graph["node-001"]["label"] == "CLASS"

    def test_add_node_with_defaults(self):
        """Test adding a node with default properties."""
        mock_neptune = MagicMock()
        adapter = NeptuneGraphAdapter(mock_neptune)

        adapter.add_node("node-002", "METHOD")

        # Should use defaults for missing properties
        mock_neptune.add_code_entity.assert_called_once()
        call_kwargs = mock_neptune.add_code_entity.call_args.kwargs
        assert call_kwargs["name"] == "node-002"
        assert call_kwargs["file_path"] == "unknown"
        assert call_kwargs["line_number"] == 1


class TestNeptuneGraphAdapterAddEdge:
    """Tests for add_edge method."""

    def test_add_edge_basic(self):
        """Test adding a basic edge."""
        mock_neptune = MagicMock()
        adapter = NeptuneGraphAdapter(mock_neptune)

        # First add source node
        adapter.ckge_graph["source-001"] = {
            "label": "CLASS",
            "properties": {},
            "edges": {},
        }

        adapter.add_edge("source-001", "target-001", "CALLS", weight=1.0)

        mock_neptune.add_relationship.assert_called_once()
        assert "CALLS" in adapter.ckge_graph["source-001"]["edges"]
        assert "target-001" in adapter.ckge_graph["source-001"]["edges"]["CALLS"]

    def test_add_edge_without_source_in_cache(self):
        """Test adding edge when source not in local cache."""
        mock_neptune = MagicMock()
        adapter = NeptuneGraphAdapter(mock_neptune)

        # Don't add source to cache
        adapter.add_edge("unknown-source", "target-001", "IMPORTS")

        # Should still call Neptune
        mock_neptune.add_relationship.assert_called_once()

    def test_add_edge_no_properties(self):
        """Test adding edge without additional properties."""
        mock_neptune = MagicMock()
        adapter = NeptuneGraphAdapter(mock_neptune)

        adapter.ckge_graph["source-001"] = {
            "label": "CLASS",
            "properties": {},
            "edges": {},
        }

        adapter.add_edge("source-001", "target-001", "CONTAINS")

        # metadata should be None when no properties
        mock_neptune.add_relationship.assert_called_with(
            from_entity="source-001",
            to_entity="target-001",
            relationship="CONTAINS",
            metadata=None,
        )

    def test_add_edge_multiple_same_type(self):
        """Test adding multiple edges of the same type."""
        mock_neptune = MagicMock()
        adapter = NeptuneGraphAdapter(mock_neptune)

        adapter.ckge_graph["source"] = {"label": "CLASS", "properties": {}, "edges": {}}

        adapter.add_edge("source", "target1", "CALLS")
        adapter.add_edge("source", "target2", "CALLS")

        assert len(adapter.ckge_graph["source"]["edges"]["CALLS"]) == 2


class TestNeptuneGraphAdapterRunGremlinQuery:
    """Tests for run_gremlin_query method."""

    def test_run_gremlin_query_with_results(self):
        """Test query returns context strings."""
        mock_neptune = MagicMock()
        mock_neptune.find_related_code.return_value = [
            {"name": "RelatedClass", "relationship": "IMPORTS"},
            {"name": "Dependency", "relationship": "CALLS"},
        ]
        adapter = NeptuneGraphAdapter(mock_neptune)

        result = adapter.run_gremlin_query("TestClass")

        assert len(result) == 1
        assert "TestClass integrates with" in result[0]
        assert "RelatedClass via IMPORTS" in result[0]

    def test_run_gremlin_query_fallback_to_search(self):
        """Test query falls back to search_by_name."""
        mock_neptune = MagicMock()
        mock_neptune.find_related_code.return_value = []
        mock_neptune.search_by_name.return_value = [
            {"id": "entity-001", "relationship": "RELATED_TO"}
        ]
        adapter = NeptuneGraphAdapter(mock_neptune)

        result = adapter.run_gremlin_query("UnknownClass")

        mock_neptune.search_by_name.assert_called_once()
        assert "UnknownClass integrates with" in result[0]

    def test_run_gremlin_query_no_results(self):
        """Test query with no results."""
        mock_neptune = MagicMock()
        mock_neptune.find_related_code.return_value = []
        mock_neptune.search_by_name.return_value = []
        adapter = NeptuneGraphAdapter(mock_neptune)

        result = adapter.run_gremlin_query("IsolatedClass")

        assert len(result) == 1
        assert "No direct dependencies found" in result[0]

    def test_run_gremlin_query_entity_with_id_not_name(self):
        """Test query handles entity with id but no name."""
        mock_neptune = MagicMock()
        mock_neptune.find_related_code.return_value = [
            {"id": "entity-123", "relationship": "USES"}
        ]
        adapter = NeptuneGraphAdapter(mock_neptune)

        result = adapter.run_gremlin_query("TestClass")

        assert "entity-123 via USES" in result[0]


class TestOpenSearchVectorAdapterInit:
    """Tests for OpenSearchVectorAdapter initialization."""

    def test_init_with_opensearch_service(self):
        """Test initialization with OpenSearch service."""
        mock_opensearch = MagicMock()

        adapter = OpenSearchVectorAdapter(mock_opensearch)

        assert adapter.opensearch == mock_opensearch
        assert adapter._embedding_client is None


class TestOpenSearchVectorAdapterGetEmbedding:
    """Tests for _get_embedding method."""

    def test_get_embedding_fallback_on_error(self):
        """Test embedding falls back to mock on error."""
        mock_opensearch = MagicMock()
        mock_opensearch.vector_dimension = 512

        adapter = OpenSearchVectorAdapter(mock_opensearch)

        # Force the embedding to fail by making boto3 unavailable
        adapter._embedding_client = None
        with patch.dict("sys.modules", {"boto3": None}):
            result = adapter._get_embedding("test text")

        # Should fall back to mock vector
        assert len(result) == 512
        assert all(v == 0.1 for v in result)

    def test_get_embedding_uses_cached_client(self):
        """Test embedding reuses cached client."""
        mock_opensearch = MagicMock()
        mock_opensearch.vector_dimension = 1024

        adapter = OpenSearchVectorAdapter(mock_opensearch)

        # Set up a mock client
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = Exception("Test failure")
        adapter._embedding_client = mock_client

        result = adapter._get_embedding("test text")

        # Should use cached client and fall back on error
        assert len(result) == 1024


class TestOpenSearchVectorAdapterRunKnnSearch:
    """Tests for run_knn_search method."""

    def test_run_knn_search_with_results(self):
        """Test KNN search returns context strings."""
        mock_opensearch = MagicMock()
        mock_opensearch.vector_dimension = 1024
        mock_opensearch.search_similar.return_value = [
            {"text": "Code documentation", "metadata": {"source": "file.py"}},
            {"text": "Function definition", "metadata": {"file_path": "main.py"}},
        ]

        adapter = OpenSearchVectorAdapter(mock_opensearch)

        with patch.object(adapter, "_get_embedding", return_value=[0.1] * 1024):
            result = adapter.run_knn_search("find related code")

            assert len(result) == 2
            assert "Code Context" in result[0]
            assert "file.py" in result[0]

    def test_run_knn_search_security_policy_detection(self):
        """Test detection of security policy content."""
        mock_opensearch = MagicMock()
        mock_opensearch.vector_dimension = 1024
        mock_opensearch.search_similar.return_value = [
            {
                "text": "Security policy: prohibited actions must be avoided",
                "metadata": {},
            },
        ]

        adapter = OpenSearchVectorAdapter(mock_opensearch)

        with patch.object(adapter, "_get_embedding", return_value=[0.1] * 1024):
            result = adapter.run_knn_search("security requirements")

            assert "Security Policy" in result[0]

    def test_run_knn_search_fallback_to_metadata_search(self):
        """Test fallback to metadata search for specific queries."""
        mock_opensearch = MagicMock()
        mock_opensearch.vector_dimension = 1024
        mock_opensearch.search_similar.return_value = []
        mock_opensearch.search_by_metadata.return_value = [
            {"text": "Hash implementation", "metadata": {"category": "cryptography"}}
        ]

        adapter = OpenSearchVectorAdapter(mock_opensearch)

        with patch.object(adapter, "_get_embedding", return_value=[0.1] * 1024):
            adapter.run_knn_search("checksum validation")

            mock_opensearch.search_by_metadata.assert_called_once()

    def test_run_knn_search_default_context(self):
        """Test default context when no results found."""
        mock_opensearch = MagicMock()
        mock_opensearch.vector_dimension = 1024
        mock_opensearch.search_similar.return_value = []
        mock_opensearch.search_by_metadata.return_value = []

        adapter = OpenSearchVectorAdapter(mock_opensearch)

        with patch.object(adapter, "_get_embedding", return_value=[0.1] * 1024):
            result = adapter.run_knn_search("random query")

            assert len(result) == 1
            assert "DataProcessor" in result[0]

    def test_run_knn_search_hash_query(self):
        """Test hash-related query triggers metadata search."""
        mock_opensearch = MagicMock()
        mock_opensearch.vector_dimension = 1024
        mock_opensearch.search_similar.return_value = []
        mock_opensearch.search_by_metadata.return_value = []

        adapter = OpenSearchVectorAdapter(mock_opensearch)

        with patch.object(adapter, "_get_embedding", return_value=[0.1] * 1024):
            adapter.run_knn_search("hash function")

            mock_opensearch.search_by_metadata.assert_called_with(
                filters={"category": "cryptography"}, limit=3
            )

    def test_run_knn_search_unknown_source(self):
        """Test handling results with no source info."""
        mock_opensearch = MagicMock()
        mock_opensearch.vector_dimension = 1024
        mock_opensearch.search_similar.return_value = [
            {"text": "Some code content", "metadata": {}},
        ]

        adapter = OpenSearchVectorAdapter(mock_opensearch)

        with patch.object(adapter, "_get_embedding", return_value=[0.1] * 1024):
            result = adapter.run_knn_search("find code")

            # Should use "unknown" as source
            assert "unknown" in result[0]


class TestCreateGraphAgent:
    """Tests for create_graph_agent factory function."""

    def test_create_graph_agent_mock_mode_explicit(self):
        """Test creating mock graph agent explicitly."""
        result = create_graph_agent(use_real=False)

        # Should return a mock GraphBuilderAgent
        assert result is not None
        assert hasattr(result, "parse_source_code")

    def test_create_graph_agent_auto_detect_mock(self):
        """Test auto-detection selects mock mode when no endpoint."""
        # Ensure no Neptune endpoint is set
        env_backup = os.environ.get("NEPTUNE_ENDPOINT")
        if "NEPTUNE_ENDPOINT" in os.environ:
            del os.environ["NEPTUNE_ENDPOINT"]

        try:
            result = create_graph_agent(use_real=None)

            # Should return mock agent
            assert result is not None
        finally:
            if env_backup:
                os.environ["NEPTUNE_ENDPOINT"] = env_backup

    def test_create_graph_agent_real_mode_success(self):
        """Test creating real Neptune adapter."""
        from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode

        with patch.object(
            NeptuneGraphService, "__init__", return_value=None
        ) as mock_init:
            mock_init.return_value = None
            # Need to also patch mode attribute
            with patch.object(
                NeptuneGraphService, "mode", NeptuneMode.MOCK, create=True
            ):
                result = create_graph_agent(use_real=True)

                assert isinstance(result, NeptuneGraphAdapter)

    def test_create_graph_agent_real_mode_fallback(self):
        """Test real mode falls back to mock on failure."""
        from src.services.neptune_graph_service import NeptuneGraphService

        with patch.object(
            NeptuneGraphService, "__init__", side_effect=Exception("Connection failed")
        ):
            result = create_graph_agent(use_real=True)

            # Should return mock agent
            assert result is not None
            assert not isinstance(result, NeptuneGraphAdapter)


class TestCreateVectorStore:
    """Tests for create_vector_store factory function."""

    def test_create_vector_store_mock_mode_explicit(self):
        """Test creating mock vector store explicitly."""
        result = create_vector_store(use_real=False)

        # Should return a mock OpenSearchVectorStore
        assert result is not None
        assert hasattr(result, "run_knn_search")

    def test_create_vector_store_auto_detect_mock(self):
        """Test auto-detection selects mock mode when no endpoint."""
        # Ensure no OpenSearch endpoint is set
        env_backup = os.environ.get("OPENSEARCH_ENDPOINT")
        if "OPENSEARCH_ENDPOINT" in os.environ:
            del os.environ["OPENSEARCH_ENDPOINT"]

        try:
            result = create_vector_store(use_real=None)

            # Should return mock store
            assert result is not None
        finally:
            if env_backup:
                os.environ["OPENSEARCH_ENDPOINT"] = env_backup

    def test_create_vector_store_real_mode_success(self):
        """Test creating real OpenSearch adapter."""
        from src.services.opensearch_vector_service import (
            OpenSearchMode,
            OpenSearchVectorService,
        )

        with patch.object(
            OpenSearchVectorService, "__init__", return_value=None
        ) as mock_init:
            mock_init.return_value = None
            with patch.object(
                OpenSearchVectorService, "mode", OpenSearchMode.MOCK, create=True
            ):
                with patch.object(
                    OpenSearchVectorService, "vector_dimension", 1024, create=True
                ):
                    result = create_vector_store(use_real=True)

                    assert isinstance(result, OpenSearchVectorAdapter)

    def test_create_vector_store_real_mode_fallback(self):
        """Test real mode falls back to mock on failure."""
        from src.services.opensearch_vector_service import OpenSearchVectorService

        with patch.object(
            OpenSearchVectorService,
            "__init__",
            side_effect=Exception("Connection failed"),
        ):
            result = create_vector_store(use_real=True)

            # Should return mock store
            assert result is not None
            assert not isinstance(result, OpenSearchVectorAdapter)


class TestProtocols:
    """Tests for protocol definitions."""

    def test_graph_agent_protocol_methods(self):
        """Test GraphAgentProtocol defines required methods."""
        from src.services.service_adapters import GraphAgentProtocol

        # Protocol should define these methods
        assert hasattr(GraphAgentProtocol, "parse_source_code")
        assert hasattr(GraphAgentProtocol, "add_node")
        assert hasattr(GraphAgentProtocol, "add_edge")
        assert hasattr(GraphAgentProtocol, "run_gremlin_query")

    def test_vector_store_protocol_methods(self):
        """Test VectorStoreProtocol defines required methods."""
        from src.services.service_adapters import VectorStoreProtocol

        # Protocol should define this method
        assert hasattr(VectorStoreProtocol, "run_knn_search")


class TestBedrockEmbeddings:
    """Tests for Bedrock embedding integration."""

    def test_get_embedding_bedrock_success(self):
        """Test _get_embedding with successful Bedrock call - covers lines 289, 297-298."""
        import io
        import json

        mock_opensearch = MagicMock()
        mock_opensearch.vector_dimension = 1024

        adapter = OpenSearchVectorAdapter(mock_opensearch)

        # Mock the Bedrock response
        mock_response_body = io.BytesIO(
            json.dumps({"embedding": [0.1] * 1024}).encode()
        )
        mock_response = {
            "body": mock_response_body,
        }

        mock_bedrock_client = MagicMock()
        mock_bedrock_client.invoke_model.return_value = mock_response

        with patch("boto3.client", return_value=mock_bedrock_client):
            # Clear the cached client to force recreation
            adapter._embedding_client = None

            embedding = adapter._get_embedding("test text")

            # Should have called Bedrock
            mock_bedrock_client.invoke_model.assert_called_once()

            # Should return the embedding from Bedrock
            assert len(embedding) == 1024
            assert embedding[0] == 0.1

    def test_get_embedding_uses_cached_client(self):
        """Test _get_embedding reuses cached Bedrock client."""
        import io
        import json

        mock_opensearch = MagicMock()
        mock_opensearch.vector_dimension = 1024

        adapter = OpenSearchVectorAdapter(mock_opensearch)

        # Pre-set a cached client
        mock_bedrock_client = MagicMock()
        mock_response_body = io.BytesIO(
            json.dumps({"embedding": [0.2] * 1024}).encode()
        )
        mock_bedrock_client.invoke_model.return_value = {"body": mock_response_body}

        adapter._embedding_client = mock_bedrock_client

        with patch("boto3.client") as mock_boto3_client:
            embedding = adapter._get_embedding("test text")

            # Should NOT have called boto3.client since we had a cached client
            mock_boto3_client.assert_not_called()

            # Should use the cached client
            mock_bedrock_client.invoke_model.assert_called_once()
            assert len(embedding) == 1024
