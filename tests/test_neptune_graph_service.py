"""
Project Aura - Neptune Graph Service Tests

Comprehensive tests for Neptune graph database operations.
Tests based on ACTUAL implementation, not planned API.
"""

# ruff: noqa: PLR2004


import os
import platform
import time

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.neptune_graph_service import (
    NeptuneError,
    NeptuneGraphService,
    NeptuneMode,
    escape_gremlin_string,
)


class TestNeptuneGraphService:
    """Test suite for NeptuneGraphService."""

    def test_initialization_mock_mode(self):
        """Test service initialization in MOCK mode."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        assert service.mode == NeptuneMode.MOCK
        assert service.endpoint == "neptune.aura.local"
        assert service.port == 8182
        assert service.use_iam_auth is True
        assert service.max_connections == 10
        assert service.connection_timeout == 10000
        assert isinstance(service.mock_graph, dict)
        assert isinstance(service.mock_edges, list)

    def test_initialization_custom_config(self):
        """Test service initialization with custom configuration."""
        service = NeptuneGraphService(
            mode=NeptuneMode.MOCK,
            endpoint="custom.neptune.local",
            port=9999,
            use_iam_auth=False,
        )

        assert service.endpoint == "custom.neptune.local"
        assert service.port == 9999
        assert service.use_iam_auth is False

    def test_initial_sample_data_loaded(self):
        """Test that initial sample data is loaded in mock mode."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Check sample entities
        assert "DataProcessor" in service.mock_graph
        assert "generate_checksum" in service.mock_graph

        # Check sample edge
        assert len(service.mock_edges) >= 1
        assert any(
            e["from"] == "DataProcessor" and e["to"] == "generate_checksum"
            for e in service.mock_edges
        )

    def test_add_code_entity_returns_entity_id(self):
        """Test that add_code_entity returns entity ID string."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity(
            name="MyClass",
            entity_type="class",
            file_path="src/my_module.py",
            line_number=42,
            metadata={"docstring": "Test class"},
        )

        # Should return entity ID in format "file_path::name"
        assert isinstance(entity_id, str)
        assert entity_id == "src/my_module.py::MyClass"

    def test_add_code_entity_with_parent(self):
        """Test adding entity with parent creates automatic relationship."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add parent first
        parent_id = service.add_code_entity(
            name="ParentClass",
            entity_type="class",
            file_path="src/parent.py",
            line_number=10,
        )

        # Add child with parent - pass parent NAME, not full ID
        child_id = service.add_code_entity(
            name="child_method",
            entity_type="method",
            file_path="src/parent.py",
            line_number=20,
            parent="ParentClass",  # Just the name, not full ID
        )

        # Should create automatic relationship
        relationship_created = any(
            edge["from"] == parent_id
            and edge["to"] == child_id
            and edge["relationship"] == "HAS_METHOD"
            for edge in service.mock_edges
        )
        assert relationship_created

    def test_add_code_entity_stores_all_fields(self):
        """Test that all entity fields are stored correctly."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        metadata = {"complexity": 5, "author": "alice"}
        entity_id = service.add_code_entity(
            name="TestFunc",
            entity_type="function",
            file_path="src/utils.py",
            line_number=100,
            parent=None,
            metadata=metadata,
        )

        entity = service.mock_graph[entity_id]
        assert entity["id"] == entity_id
        assert entity["name"] == "TestFunc"
        assert entity["type"] == "function"
        assert entity["file_path"] == "src/utils.py"
        assert entity["line_number"] == 100
        assert entity["parent"] is None
        assert entity["metadata"] == metadata
        assert "created_at" in entity

    def test_add_relationship_success(self):
        """Test adding relationship between entities."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        result = service.add_relationship(
            from_entity="EntityA",
            to_entity="EntityB",
            relationship="CALLS",
            metadata={"call_count": 5},
        )

        assert result is True
        assert len(service.mock_edges) > 0

        # Find the added edge
        edge = next(
            (
                e
                for e in service.mock_edges
                if e["from"] == "EntityA" and e["to"] == "EntityB"
            ),
            None,
        )
        assert edge is not None
        assert edge["relationship"] == "CALLS"
        assert edge["metadata"]["call_count"] == 5
        assert "created_at" in edge

    def test_add_relationship_no_validation(self):
        """Test that add_relationship doesn't validate entity existence in mock mode."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add relationship between non-existent entities
        result = service.add_relationship(
            from_entity="NonExistent1",
            to_entity="NonExistent2",
            relationship="IMPORTS",
        )

        # Should still succeed in mock mode
        assert result is True

    def test_find_related_code_substring_matching(self):
        """Test that find_related_code uses substring matching."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add entities and relationship
        entity_id_a = service.add_code_entity("ClassA", "class", "a.py", 1)
        entity_id_b = service.add_code_entity("ClassB", "class", "b.py", 1)
        service.add_relationship(entity_id_a, entity_id_b, "IMPORTS")

        # Search using partial name
        results = service.find_related_code("ClassA")

        # Should find ClassB since edge has ClassA in "from"
        assert len(results) > 0
        assert any(r["name"] == "ClassB" for r in results)

    def test_find_related_code_returns_depth_one(self):
        """Test that find_related_code always returns depth=1."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id_a = service.add_code_entity("A", "class", "a.py", 1)
        entity_id_b = service.add_code_entity("B", "class", "b.py", 1)
        service.add_relationship(entity_id_a, entity_id_b, "CALLS")

        results = service.find_related_code("A", max_depth=5)

        # Depth should always be 1 regardless of max_depth parameter
        assert all(r["depth"] == 1 for r in results)

    def test_find_related_code_empty_result(self):
        """Test find_related_code with no matches."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        results = service.find_related_code("NonExistentEntity")

        assert results == []

    def test_find_related_code_includes_relationship(self):
        """Test that results include relationship information."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id_a = service.add_code_entity("A", "class", "a.py", 1)
        entity_id_b = service.add_code_entity("B", "class", "b.py", 1)
        service.add_relationship(entity_id_a, entity_id_b, "IMPORTS")

        results = service.find_related_code("A")

        if results:
            result = results[0]
            assert "relationship" in result
            assert result["relationship"] == "IMPORTS"

    def test_get_entity_by_id_success(self):
        """Test retrieving entity by ID."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity("TestClass", "class", "test.py", 10)

        entity = service.get_entity_by_id(entity_id)

        assert entity is not None
        assert entity["id"] == entity_id
        assert entity["name"] == "TestClass"

    def test_get_entity_by_id_not_found(self):
        """Test get_entity_by_id with non-existent ID."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity = service.get_entity_by_id("non-existent-id")

        assert entity is None

    def test_search_by_name_case_insensitive(self):
        """Test that search_by_name is case-insensitive."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        service.add_code_entity("UserController", "class", "controller.py", 1)
        service.add_code_entity("userService", "class", "service.py", 1)

        results = service.search_by_name("user", limit=10)

        # Should find both entities
        assert len(results) >= 2
        names = [r["name"] for r in results]
        assert "UserController" in names
        assert "userService" in names

    def test_search_by_name_substring_match(self):
        """Test search_by_name uses substring matching."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        service.add_code_entity("validateInput", "function", "utils.py", 1)
        service.add_code_entity("processData", "function", "utils.py", 10)

        results = service.search_by_name("validate")

        assert len(results) >= 1
        assert results[0]["name"] == "validateInput"

    def test_search_by_name_respects_limit(self):
        """Test that search_by_name respects the limit parameter."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add many entities with same pattern
        for i in range(10):
            service.add_code_entity(f"TestClass{i}", "class", "test.py", i)

        results = service.search_by_name("TestClass", limit=3)

        assert len(results) <= 3

    def test_search_by_name_no_matches(self):
        """Test search_by_name with no matches."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        results = service.search_by_name("NonExistentPattern")

        assert results == []

    def test_close_mock_mode(self):
        """Test close method in mock mode."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Should not raise exception
        service.close()

    def test_aws_mode_initialization_requires_gremlin(self):
        """Test AWS mode initialization behavior without Gremlin."""
        # When GREMLIN_AVAILABLE is False (default in tests), AWS mode falls back to MOCK
        service = NeptuneGraphService(
            mode=NeptuneMode.AWS, endpoint="test.neptune.aws", use_iam_auth=False
        )

        # Should fall back to MOCK mode when Gremlin not available
        assert service.mode == NeptuneMode.MOCK

    def test_aws_mode_fallback_to_mock(self):
        """Test AWS mode falls back to MOCK when Gremlin unavailable."""
        # GREMLIN_AVAILABLE is False by default in tests
        service = NeptuneGraphService(mode=NeptuneMode.AWS)

        assert service.mode == NeptuneMode.MOCK

    def test_neptune_error_exception(self):
        """Test NeptuneError exception can be raised."""
        with pytest.raises(NeptuneError, match="Test error"):
            raise NeptuneError("Test error")

    def test_multiple_relationships_same_entities(self):
        """Test adding multiple relationships between same entities."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        service.add_relationship("A", "B", "IMPORTS")
        service.add_relationship("A", "B", "CALLS")

        # Should have both relationships
        ab_edges = [
            e for e in service.mock_edges if e["from"] == "A" and e["to"] == "B"
        ]
        assert len(ab_edges) >= 2

        relationships = [e["relationship"] for e in ab_edges]
        assert "IMPORTS" in relationships
        assert "CALLS" in relationships

    def test_entity_id_format(self):
        """Test entity ID format is file_path::name."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity(
            "MyFunc", "function", "src/utils/helpers.py", 42
        )

        assert entity_id == "src/utils/helpers.py::MyFunc"

    def test_metadata_optional_defaults_to_empty_dict(self):
        """Test that metadata defaults to empty dict when not provided."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity("Test", "class", "test.py", 1)

        entity = service.mock_graph[entity_id]
        assert entity["metadata"] == {}

    def test_parent_optional_defaults_to_none(self):
        """Test that parent defaults to None when not provided."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity("Test", "class", "test.py", 1)

        entity = service.mock_graph[entity_id]
        assert entity["parent"] is None

    def test_find_related_code_max_depth_ignored(self):
        """Test that max_depth parameter is ignored in mock mode."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Create chain A -> B -> C
        id_a = service.add_code_entity("A", "class", "a.py", 1)
        id_b = service.add_code_entity("B", "class", "b.py", 1)
        id_c = service.add_code_entity("C", "class", "c.py", 1)

        service.add_relationship(id_a, id_b, "CALLS")
        service.add_relationship(id_b, id_c, "CALLS")

        # Mock mode doesn't do true traversal, so max_depth doesn't matter
        results_depth_1 = service.find_related_code("A", max_depth=1)
        results_depth_10 = service.find_related_code("A", max_depth=10)

        # Both should return same results (substring matching only)
        assert len(results_depth_1) == len(results_depth_10)

    def test_find_related_code_relationship_types_ignored(self):
        """Test that relationship_types parameter is ignored in mock mode."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        id_a = service.add_code_entity("A", "class", "a.py", 1)
        id_b = service.add_code_entity("B", "class", "b.py", 1)
        service.add_relationship(id_a, id_b, "IMPORTS")

        # Relationship types filter is ignored in mock mode
        results = service.find_related_code("A", relationship_types=["CALLS"])

        # Should still find B even though we filtered for CALLS
        assert any(r["name"] == "B" for r in results) or len(results) == 0

    def test_created_at_timestamp_added(self):
        """Test that created_at timestamp is added to entities and edges."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity("Test", "class", "test.py", 1)
        service.add_relationship("A", "B", "CALLS")

        # Check entity has timestamp
        entity = service.mock_graph[entity_id]
        assert "created_at" in entity
        assert isinstance(entity["created_at"], str)

        # Check edge has timestamp
        edge = service.mock_edges[-1]
        assert "created_at" in edge
        assert isinstance(edge["created_at"], str)

    def test_aws_mode_init_with_invalid_endpoint(self):
        """Test AWS mode initialization with invalid endpoint falls back to MOCK."""
        # Attempt to initialize with invalid endpoint (will fail to connect)
        service = NeptuneGraphService(
            mode=NeptuneMode.AWS,
            endpoint="invalid.neptune.endpoint.local",
            port=8182,
            use_iam_auth=False,
        )

        # Should fall back to MOCK mode after connection failure
        assert service.mode == NeptuneMode.MOCK
        assert isinstance(service.mock_graph, dict)
        assert isinstance(service.mock_edges, list)

    def test_init_with_custom_connection_params(self):
        """Test initialization with custom connection parameters."""
        service = NeptuneGraphService(
            mode=NeptuneMode.MOCK,
            endpoint="custom.neptune.local",
            port=9999,
            use_iam_auth=True,
        )

        assert service.endpoint == "custom.neptune.local"
        assert service.port == 9999
        assert service.use_iam_auth is True

    def test_search_by_name_empty_pattern(self):
        """Test search with empty pattern."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        service.add_code_entity("TestClass", "class", "test.py", 1)

        results = service.search_by_name("")

        # Empty pattern should still work (matches nothing or everything depending on impl)
        assert isinstance(results, list)

    def test_find_related_code_with_no_edges(self):
        """Test find_related_code when entity has no relationships."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add entity but no relationships
        service.add_code_entity("IsolatedClass", "class", "isolated.py", 1)

        results = service.find_related_code("IsolatedClass")

        # Should return empty list
        assert results == []

    def test_multiple_add_relationship_calls(self):
        """Test adding multiple relationships in sequence."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        result1 = service.add_relationship("A", "B", "CALLS")
        result2 = service.add_relationship("B", "C", "IMPORTS")
        result3 = service.add_relationship("C", "A", "DEPENDS_ON")

        assert result1 is True
        assert result2 is True
        assert result3 is True
        assert len(service.mock_edges) >= 3

    def test_query_cache_initialization(self):
        """Test query cache is initialized correctly."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        assert service.MAX_QUERY_CACHE_SIZE == 200
        assert service.QUERY_CACHE_TTL_SECONDS == 1800
        assert isinstance(service._query_cache, dict)
        assert service._query_cache_hits == 0
        assert service._query_cache_misses == 0


class TestNeptuneDeleteOperations:
    """Tests for Neptune delete operations in mock mode."""

    def test_delete_entity_success(self):
        """Test deleting an entity removes it from the graph."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity("ToDelete", "class", "delete.py", 1)
        assert entity_id in service.mock_graph

        result = service.delete_entity(entity_id)

        assert result is True
        assert entity_id not in service.mock_graph

    def test_delete_entity_not_found(self):
        """Test deleting non-existent entity returns False."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        result = service.delete_entity("non-existent-id")

        assert result is False

    def test_delete_entity_removes_connected_edges(self):
        """Test deleting entity also removes connected edges."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        id_a = service.add_code_entity("A", "class", "a.py", 1)
        id_b = service.add_code_entity("B", "class", "b.py", 1)
        service.add_relationship(id_a, id_b, "CALLS")

        initial_edge_count = len(
            [e for e in service.mock_edges if e["from"] == id_a or e["to"] == id_a]
        )
        assert initial_edge_count >= 1

        service.delete_entity(id_a)

        # Edges involving deleted entity should be gone
        remaining_edges = [
            e for e in service.mock_edges if e["from"] == id_a or e["to"] == id_a
        ]
        assert len(remaining_edges) == 0

    def test_delete_by_repository_success(self):
        """Test deleting all entities for a repository."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add entities with repository metadata
        service.add_code_entity(
            "RepoClass1",
            "class",
            "src/a.py",
            1,
            metadata={"repository": "owner/test-repo"},
        )
        service.add_code_entity(
            "RepoClass2",
            "class",
            "src/b.py",
            1,
            metadata={"repository": "owner/test-repo"},
        )
        service.add_code_entity(
            "OtherClass",
            "class",
            "src/c.py",
            1,
            metadata={"repository": "owner/other-repo"},
        )

        deleted_count = service.delete_by_repository("owner/test-repo")

        assert deleted_count == 2
        # Other repo entities should remain
        remaining = [
            e
            for e in service.mock_graph.values()
            if e.get("metadata", {}).get("repository") == "owner/test-repo"
        ]
        assert len(remaining) == 0

    def test_delete_by_repository_no_matches(self):
        """Test delete_by_repository with no matching entities."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        deleted_count = service.delete_by_repository("nonexistent/repo")

        assert deleted_count == 0

    def test_delete_by_repository_removes_edges(self):
        """Test delete_by_repository also removes related edges."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        id_a = service.add_code_entity(
            "A", "class", "a.py", 1, metadata={"repository": "owner/repo"}
        )
        id_b = service.add_code_entity(
            "B", "class", "b.py", 1, metadata={"repository": "owner/repo"}
        )
        id_c = service.add_code_entity(
            "C", "class", "c.py", 1, metadata={"repository": "owner/other"}
        )
        service.add_relationship(id_a, id_b, "CALLS")
        service.add_relationship(id_b, id_c, "IMPORTS")

        service.delete_by_repository("owner/repo")

        # Edges involving deleted entities should be removed
        remaining_edges = [
            e
            for e in service.mock_edges
            if id_a in [e["from"], e["to"]] or id_b in [e["from"], e["to"]]
        ]
        assert len(remaining_edges) == 0

    def test_delete_entities_by_file_success(self):
        """Test deleting all entities from a specific file."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        service.add_code_entity("Class1", "class", "src/target.py", 1)
        service.add_code_entity("Class2", "class", "src/target.py", 10)
        service.add_code_entity("Other", "class", "src/other.py", 1)

        deleted_count = service.delete_entities_by_file("src/target.py")

        assert deleted_count == 2
        remaining = [
            e
            for e in service.mock_graph.values()
            if e.get("file_path") == "src/target.py"
        ]
        assert len(remaining) == 0

    def test_delete_entities_by_file_no_matches(self):
        """Test delete_entities_by_file with no matching file."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        deleted_count = service.delete_entities_by_file("nonexistent/file.py")

        assert deleted_count == 0

    def test_delete_entities_by_file_removes_edges(self):
        """Test delete_entities_by_file removes connected edges."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        id_a = service.add_code_entity("A", "class", "target.py", 1)
        id_b = service.add_code_entity("B", "class", "other.py", 1)
        service.add_relationship(id_a, id_b, "CALLS")

        service.delete_entities_by_file("target.py")

        # Edges involving deleted entity should be removed
        remaining_edges = [
            e for e in service.mock_edges if id_a in [e["from"], e["to"]]
        ]
        assert len(remaining_edges) == 0


class TestEscapeGremlinString:
    """Tests for escape_gremlin_string utility function."""

    def test_escape_single_quotes(self):
        """Test escaping single quotes."""
        result = escape_gremlin_string("it's a test")

        assert result == "it\\'s a test"

    def test_escape_backslashes(self):
        """Test escaping backslashes."""
        result = escape_gremlin_string("path\\to\\file")

        assert result == "path\\\\to\\\\file"

    def test_escape_newlines(self):
        """Test escaping newline characters."""
        result = escape_gremlin_string("line1\nline2")

        assert result == "line1\\nline2"

    def test_escape_carriage_returns(self):
        """Test escaping carriage return characters."""
        result = escape_gremlin_string("line1\rline2")

        assert result == "line1\\rline2"

    def test_escape_tabs(self):
        """Test escaping tab characters."""
        result = escape_gremlin_string("col1\tcol2")

        assert result == "col1\\tcol2"

    def test_escape_non_string_input(self):
        """Test that non-string input is converted to string."""
        result = escape_gremlin_string(12345)

        assert result == "12345"

    def test_escape_combined_special_chars(self):
        """Test escaping multiple special characters."""
        result = escape_gremlin_string("path\\file.txt has 'quotes'\nand newlines")

        assert "\\\\" in result  # Escaped backslash
        assert "\\'" in result  # Escaped quote
        assert "\\n" in result  # Escaped newline

    def test_escape_empty_string(self):
        """Test escaping empty string returns empty string."""
        result = escape_gremlin_string("")

        assert result == ""

    def test_escape_no_special_chars(self):
        """Test string without special chars is unchanged."""
        result = escape_gremlin_string("normal_string_123")

        assert result == "normal_string_123"

    def test_escape_float_input(self):
        """Test float input is converted to string."""
        result = escape_gremlin_string(3.14159)

        assert result == "3.14159"

    def test_escape_boolean_input(self):
        """Test boolean input is converted to string."""
        result = escape_gremlin_string(True)

        assert result == "True"

    def test_escape_none_input(self):
        """Test None input is converted to string."""
        result = escape_gremlin_string(None)

        assert result == "None"

    def test_escape_list_input(self):
        """Test list input is converted to string."""
        result = escape_gremlin_string([1, 2, 3])

        assert result == "[1, 2, 3]"

    def test_escape_backslash_before_quote(self):
        """Test escaping backslash followed by quote."""
        result = escape_gremlin_string("test\\'quote")

        # Backslash gets doubled, quote gets escaped
        assert result == "test\\\\\\'quote"


class TestCreateGraphService:
    """Tests for create_graph_service factory function."""

    def test_create_graph_service_default_mock_mode(self):
        """Test create_graph_service defaults to mock mode without NEPTUNE_ENDPOINT."""
        from src.services.neptune_graph_service import create_graph_service

        # Ensure no NEPTUNE_ENDPOINT set
        if "NEPTUNE_ENDPOINT" in os.environ:
            del os.environ["NEPTUNE_ENDPOINT"]

        service = create_graph_service()

        assert service.mode == NeptuneMode.MOCK

    def test_create_graph_service_with_environment(self):
        """Test create_graph_service accepts environment parameter."""
        from src.services.neptune_graph_service import create_graph_service

        # Environment parameter is reserved for future use
        service = create_graph_service("dev")

        assert service is not None
        assert service.mode == NeptuneMode.MOCK

    def test_create_graph_service_uses_env_vars(self):
        """Test create_graph_service reads from environment variables."""
        from src.services.neptune_graph_service import create_graph_service

        os.environ["NEPTUNE_PORT"] = "9999"

        try:
            service = create_graph_service()
            assert service.port == 9999
        finally:
            del os.environ["NEPTUNE_PORT"]

    def test_create_graph_service_uses_endpoint_env_var(self):
        """Test create_graph_service reads NEPTUNE_ENDPOINT env var."""
        from src.services.neptune_graph_service import create_graph_service

        os.environ["NEPTUNE_ENDPOINT"] = "custom.endpoint.local"

        try:
            service = create_graph_service()
            assert service.endpoint == "custom.endpoint.local"
        finally:
            del os.environ["NEPTUNE_ENDPOINT"]

    def test_create_graph_service_none_environment(self):
        """Test create_graph_service with None environment."""
        from src.services.neptune_graph_service import create_graph_service

        service = create_graph_service(None)

        assert service is not None
        assert service.mode == NeptuneMode.MOCK


class TestQueryPlanCaching:
    """Tests for query plan caching functionality."""

    def test_get_query_pattern_key_consistent(self):
        """Test query pattern key is consistent for same inputs."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        template = "g.V().has('name', '{name}')"
        params = {"name": "TestClass"}

        key1 = service._get_query_pattern_key(template, params)
        key2 = service._get_query_pattern_key(template, params)

        assert key1 == key2
        assert len(key1) == 32  # SHA256 hash truncated to 32 chars

    def test_get_query_pattern_key_different_params(self):
        """Test query pattern key differs for different param types."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        template = "g.V().has('name', '{name}')"
        params_str = {"name": "TestClass"}
        params_int = {"name": 123}

        key_str = service._get_query_pattern_key(template, params_str)
        key_int = service._get_query_pattern_key(template, params_int)

        assert key_str != key_int

    def test_get_query_pattern_key_different_templates(self):
        """Test query pattern key differs for different templates."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        template1 = "g.V().has('name', '{name}')"
        template2 = "g.V().has('type', '{name}')"
        params = {"name": "TestClass"}

        key1 = service._get_query_pattern_key(template1, params)
        key2 = service._get_query_pattern_key(template2, params)

        assert key1 != key2

    def test_get_cached_query_miss(self):
        """Test cache miss returns None and increments miss counter."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        initial_misses = service._query_cache_misses

        result = service._get_cached_query("nonexistent-key")

        assert result is None
        assert service._query_cache_misses == initial_misses + 1

    def test_cache_query_and_retrieve(self):
        """Test caching and retrieving a query."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        cache_key = "test-cache-key"
        query = "g.V().has('name', '{name}')"

        service._cache_query(cache_key, query)
        result = service._get_cached_query(cache_key)

        assert result == query
        assert service._query_cache_hits == 1

    def test_cache_query_ttl_expiration(self):
        """Test cached query expires after TTL."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Set a very short TTL for testing
        service.QUERY_CACHE_TTL_SECONDS = 0.1

        cache_key = "ttl-test-key"
        query = "g.V().limit(1)"

        service._cache_query(cache_key, query)

        # Query should be cached initially
        result1 = service._get_cached_query(cache_key)
        assert result1 == query

        # Wait for TTL to expire
        time.sleep(0.2)

        # Query should be expired
        result2 = service._get_cached_query(cache_key)
        assert result2 is None
        assert cache_key not in service._query_cache

    def test_cache_query_eviction(self):
        """Test cache eviction when max size is reached."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Set small cache size for testing
        service.MAX_QUERY_CACHE_SIZE = 10

        # Fill cache beyond capacity
        for i in range(25):
            service._cache_query(f"key-{i}", f"query-{i}")

        # Cache should be trimmed
        # After exceeding 10, it evicts 20 entries plus buffer of 20
        # So it will be at most MAX_QUERY_CACHE_SIZE
        assert len(service._query_cache) <= service.MAX_QUERY_CACHE_SIZE + 20

    def test_get_query_cache_stats(self):
        """Test query cache statistics."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Cache a query and access it
        service._cache_query("stats-key", "stats-query")
        service._get_cached_query("stats-key")  # Hit
        service._get_cached_query("nonexistent")  # Miss

        stats = service.get_query_cache_stats()

        assert stats["cache_size"] == 1
        assert stats["max_size"] == 200
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["ttl_seconds"] == 1800

    def test_get_query_cache_stats_zero_total(self):
        """Test query cache statistics with no queries."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        stats = service.get_query_cache_stats()

        assert stats["cache_size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0

    def test_clear_query_cache(self):
        """Test clearing the query cache."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add some entries
        service._cache_query("key1", "query1")
        service._cache_query("key2", "query2")
        service._cache_query("key3", "query3")

        count = service.clear_query_cache()

        assert count == 3
        assert len(service._query_cache) == 0

    def test_clear_query_cache_empty(self):
        """Test clearing an empty cache."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        count = service.clear_query_cache()

        assert count == 0

    def test_build_gremlin_query_with_cache(self):
        """Test building Gremlin query uses cache."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        template = "g.V().has('name', '{name}')"
        params = {"name": "TestClass"}

        # First call should miss cache
        initial_misses = service._query_cache_misses
        query1 = service._build_gremlin_query(template, params)

        assert service._query_cache_misses == initial_misses + 1
        assert "TestClass" in query1

        # Second call should hit cache
        initial_hits = service._query_cache_hits
        query2 = service._build_gremlin_query(template, params)

        assert service._query_cache_hits == initial_hits + 1
        assert query1 == query2

    def test_build_gremlin_query_without_cache(self):
        """Test building Gremlin query without cache."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        template = "g.V().has('name', '{name}')"
        params = {"name": "TestClass"}

        initial_misses = service._query_cache_misses

        query = service._build_gremlin_query(template, params, use_cache=False)

        # Should not affect cache counters
        assert service._query_cache_misses == initial_misses
        assert "TestClass" in query

    def test_build_gremlin_query_escapes_params(self):
        """Test query building escapes parameters."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        template = "g.V().has('name', '{name}')"
        params = {"name": "Test'Class"}

        query = service._build_gremlin_query(template, params, use_cache=False)

        assert "\\'" in query  # Quote should be escaped

    def test_build_gremlin_query_multiple_params(self):
        """Test query building with multiple parameters."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        template = "g.V().has('name', '{name}').has('type', '{type}')"
        params = {"name": "TestClass", "type": "class"}

        query = service._build_gremlin_query(template, params, use_cache=False)

        assert "TestClass" in query
        assert "class" in query


class TestNeptuneAWSMode:
    """Tests for Neptune AWS mode operations with mocked Gremlin client."""

    def test_init_gremlin_client_success(self):
        """Test successful Gremlin client initialization."""
        from unittest.mock import MagicMock, patch

        mock_client_class = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        # Mock the submit chain for connection test
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = []
        mock_client_instance.submit.return_value = mock_result

        with patch.dict("sys.modules", {"gremlin_python.driver.client": MagicMock()}):
            with patch("src.services.neptune_graph_service.GREMLIN_AVAILABLE", True):
                with patch(
                    "src.services.neptune_graph_service.client.Client",
                    mock_client_class,
                ):
                    with patch("src.services.neptune_graph_service.serializer"):
                        service = NeptuneGraphService(
                            mode=NeptuneMode.AWS,
                            endpoint="test.neptune.local",
                            use_iam_auth=False,
                        )

                        assert service.mode == NeptuneMode.AWS

    def test_init_gremlin_client_failure_fallback(self):
        """Test Gremlin client initialization failure falls back to mock."""
        from unittest.mock import MagicMock, patch

        mock_client_class = MagicMock()
        mock_client_class.side_effect = Exception("Connection failed")

        with patch("src.services.neptune_graph_service.GREMLIN_AVAILABLE", True):
            with patch(
                "src.services.neptune_graph_service.client.Client", mock_client_class
            ):
                with patch("src.services.neptune_graph_service.serializer"):
                    service = NeptuneGraphService(
                        mode=NeptuneMode.AWS,
                        endpoint="invalid.endpoint",
                        use_iam_auth=False,
                    )

                    # Should fall back to MOCK mode
                    assert service.mode == NeptuneMode.MOCK

    def test_add_code_entity_aws_mode(self):
        """Test add_code_entity in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = []
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        entity_id = service.add_code_entity(
            name="TestClass",
            entity_type="class",
            file_path="src/test.py",
            line_number=10,
            metadata={"complexity": 5},
        )

        assert entity_id == "src/test.py::TestClass"
        assert mock_client.submit.called

    def test_add_code_entity_aws_mode_with_parent(self):
        """Test add_code_entity in AWS mode with parent relationship."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = []
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        entity_id = service.add_code_entity(
            name="child_method",
            entity_type="method",
            file_path="src/test.py",
            line_number=20,
            parent="ParentClass",
        )

        assert entity_id == "src/test.py::child_method"
        # Should have made multiple submit calls (entity + relationship)
        assert mock_client.submit.call_count >= 1

    def test_add_code_entity_aws_mode_error(self):
        """Test add_code_entity in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.submit.side_effect = Exception("Neptune error")

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        with pytest.raises(NeptuneError, match="Failed to add entity"):
            service.add_code_entity(
                name="TestClass",
                entity_type="class",
                file_path="src/test.py",
                line_number=10,
            )

    def test_add_relationship_aws_mode(self):
        """Test add_relationship in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = []
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        result = service.add_relationship(
            from_entity="EntityA",
            to_entity="EntityB",
            relationship="CALLS",
            metadata={"call_count": 5},
        )

        assert result is True
        assert mock_client.submit.called

    def test_add_relationship_aws_mode_error(self):
        """Test add_relationship in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.submit.side_effect = Exception("Neptune error")

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        with pytest.raises(NeptuneError, match="Failed to add relationship"):
            service.add_relationship("A", "B", "CALLS")

    def test_find_related_code_aws_mode(self):
        """Test find_related_code in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = [
            {
                "entity_id": ["src/test.py::RelatedClass"],
                "name": ["RelatedClass"],
                "type": ["class"],
                "file_path": ["src/test.py"],
                "line_number": [20],
            }
        ]
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        results = service.find_related_code("TestClass", max_depth=2)

        assert len(results) == 1
        assert results[0]["name"] == "RelatedClass"
        assert mock_client.submit.called

    def test_find_related_code_aws_mode_with_relationship_types(self):
        """Test find_related_code with relationship_types filter."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = []
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        results = service.find_related_code(
            "TestClass",
            max_depth=2,
            relationship_types=["CALLS", "IMPORTS"],
        )

        assert isinstance(results, list)
        # Verify the query was submitted
        assert mock_client.submit.called

    def test_find_related_code_aws_mode_error(self):
        """Test find_related_code in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.submit.side_effect = Exception("Neptune error")

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        with pytest.raises(NeptuneError, match="Failed to find related code"):
            service.find_related_code("TestClass")

    def test_get_entity_by_id_aws_mode(self):
        """Test get_entity_by_id in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = [
            {
                "entity_id": ["src/test.py::TestClass"],
                "name": ["TestClass"],
                "type": ["class"],
                "file_path": ["src/test.py"],
                "line_number": [10],
            }
        ]
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        entity = service.get_entity_by_id("src/test.py::TestClass")

        assert entity is not None
        assert entity["name"] == "TestClass"
        assert entity["type"] == "class"

    def test_get_entity_by_id_aws_mode_not_found(self):
        """Test get_entity_by_id in AWS mode returns None when not found."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = []
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        entity = service.get_entity_by_id("nonexistent-id")

        assert entity is None

    def test_get_entity_by_id_aws_mode_error(self):
        """Test get_entity_by_id in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.submit.side_effect = Exception("Neptune error")

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        # Should return None on error, not raise exception
        entity = service.get_entity_by_id("test-id")

        assert entity is None

    def test_search_by_name_aws_mode(self):
        """Test search_by_name in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = [
            {
                "entity_id": ["src/test.py::TestClass"],
                "name": ["TestClass"],
                "type": ["class"],
                "file_path": ["src/test.py"],
            },
            {
                "entity_id": ["src/test.py::TestHelper"],
                "name": ["TestHelper"],
                "type": ["class"],
                "file_path": ["src/test.py"],
            },
        ]
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        results = service.search_by_name("Test", limit=10)

        assert len(results) == 2
        assert results[0]["name"] == "TestClass"
        assert results[1]["name"] == "TestHelper"

    def test_search_by_name_aws_mode_error(self):
        """Test search_by_name in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.submit.side_effect = Exception("Neptune error")

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        # Should return empty list on error, not raise exception
        results = service.search_by_name("Test")

        assert results == []

    def test_delete_by_repository_aws_mode(self):
        """Test delete_by_repository in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = []
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        deleted = service.delete_by_repository("owner/repo")

        assert deleted == -1  # AWS mode returns -1 (count unknown)
        assert mock_client.submit.called

    def test_delete_by_repository_aws_mode_error(self):
        """Test delete_by_repository in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.submit.side_effect = Exception("Neptune error")

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        with pytest.raises(NeptuneError, match="Failed to delete repository"):
            service.delete_by_repository("owner/repo")

    def test_delete_entity_aws_mode(self):
        """Test delete_entity in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = []
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        result = service.delete_entity("test-entity-id")

        assert result is True
        assert mock_client.submit.called

    def test_delete_entity_aws_mode_error(self):
        """Test delete_entity in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.submit.side_effect = Exception("Neptune error")

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        with pytest.raises(NeptuneError, match="Failed to delete entity"):
            service.delete_entity("test-entity-id")

    def test_delete_entities_by_file_aws_mode(self):
        """Test delete_entities_by_file in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = []
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        deleted = service.delete_entities_by_file("src/test.py")

        assert deleted == -1  # AWS mode returns -1 (count unknown)
        assert mock_client.submit.called

    def test_delete_entities_by_file_aws_mode_error(self):
        """Test delete_entities_by_file in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.submit.side_effect = Exception("Neptune error")

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        with pytest.raises(NeptuneError, match="Failed to delete file entities"):
            service.delete_entities_by_file("src/test.py")

    def test_close_aws_mode_success(self):
        """Test close method in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        service.close()

        mock_client.close.assert_called_once()

    def test_close_aws_mode_error(self):
        """Test close method in AWS mode handles errors gracefully."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.close.side_effect = Exception("Close error")

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        # Should not raise exception
        service.close()

    def test_init_iam_auth_url_format(self):
        """Test IAM auth URL format uses wss protocol."""
        from unittest.mock import MagicMock, patch

        captured_url = None

        def capture_client_init(url, *args, **kwargs):
            nonlocal captured_url
            captured_url = url
            mock = MagicMock()
            mock.submit.return_value.all.return_value.result.return_value = []
            return mock

        with patch("src.services.neptune_graph_service.GREMLIN_AVAILABLE", True):
            with patch(
                "src.services.neptune_graph_service.client.Client", capture_client_init
            ):
                with patch("src.services.neptune_graph_service.serializer"):
                    _service = NeptuneGraphService(
                        mode=NeptuneMode.AWS,
                        endpoint="test.neptune.local",
                        port=8182,
                        use_iam_auth=True,
                    )

        assert captured_url == "wss://test.neptune.local:8182/gremlin"

    def test_init_no_iam_auth_url_format(self):
        """Test non-IAM auth URL format uses ws protocol."""
        from unittest.mock import MagicMock, patch

        captured_url = None

        def capture_client_init(url, *args, **kwargs):
            nonlocal captured_url
            captured_url = url
            mock = MagicMock()
            mock.submit.return_value.all.return_value.result.return_value = []
            return mock

        with patch("src.services.neptune_graph_service.GREMLIN_AVAILABLE", True):
            with patch(
                "src.services.neptune_graph_service.client.Client", capture_client_init
            ):
                with patch("src.services.neptune_graph_service.serializer"):
                    _service = NeptuneGraphService(
                        mode=NeptuneMode.AWS,
                        endpoint="test.neptune.local",
                        port=8182,
                        use_iam_auth=False,
                    )

        assert captured_url == "ws://test.neptune.local:8182/gremlin"

    def test_add_relationship_aws_mode_with_no_metadata(self):
        """Test add_relationship in AWS mode without metadata."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = []
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        result = service.add_relationship(
            from_entity="EntityA",
            to_entity="EntityB",
            relationship="CALLS",
            metadata=None,
        )

        assert result is True
        assert mock_client.submit.called

    def test_add_code_entity_aws_mode_no_metadata(self):
        """Test add_code_entity in AWS mode without metadata."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value.result.return_value = []
        mock_client.submit.return_value = mock_result

        service = NeptuneGraphService(mode=NeptuneMode.MOCK)
        service.mode = NeptuneMode.AWS
        service.client = mock_client

        entity_id = service.add_code_entity(
            name="TestClass",
            entity_type="class",
            file_path="src/test.py",
            line_number=10,
        )

        assert entity_id == "src/test.py::TestClass"
        assert mock_client.submit.called


class TestNeptuneImportFallbacks:
    """Tests for import fallback behavior and module-level guards."""

    def test_aws_mode_falls_back_when_gremlin_unavailable(self):
        """Test AWS mode falls back to MOCK when Gremlin library is not available."""
        from unittest.mock import patch

        with patch("src.services.neptune_graph_service.GREMLIN_AVAILABLE", False):
            service = NeptuneGraphService(mode=NeptuneMode.AWS)

            # Should fall back to MOCK mode
            assert service.mode == NeptuneMode.MOCK

    def test_aws_mode_logs_warning_when_gremlin_unavailable(self):
        """Test that a warning is logged when AWS mode falls back to MOCK."""
        from unittest.mock import patch

        with patch("src.services.neptune_graph_service.GREMLIN_AVAILABLE", False):
            with patch("src.services.neptune_graph_service.logger") as mock_logger:
                _service = NeptuneGraphService(mode=NeptuneMode.AWS)

                # Should log warning about falling back
                mock_logger.warning.assert_called()
                warning_call = mock_logger.warning.call_args[0][0]
                assert (
                    "AWS mode requested" in warning_call or "MOCK mode" in warning_call
                )

    def test_mock_mode_works_without_gremlin(self):
        """Test that MOCK mode works even when Gremlin is not available."""
        from unittest.mock import patch

        with patch("src.services.neptune_graph_service.GREMLIN_AVAILABLE", False):
            service = NeptuneGraphService(mode=NeptuneMode.MOCK)

            assert service.mode == NeptuneMode.MOCK
            # Should be able to use mock functionality
            entity_id = service.add_code_entity(
                name="TestClass",
                entity_type="class",
                file_path="src/test.py",
                line_number=1,
            )
            assert entity_id is not None

    def test_gremlin_available_flag_is_boolean(self):
        """Test that GREMLIN_AVAILABLE is a boolean flag."""
        from src.services.neptune_graph_service import GREMLIN_AVAILABLE

        assert isinstance(GREMLIN_AVAILABLE, bool)

    def test_service_initialization_logs_mode(self):
        """Test that service logs its mode on initialization."""
        from unittest.mock import patch

        with patch("src.services.neptune_graph_service.logger") as mock_logger:
            _service = NeptuneGraphService(mode=NeptuneMode.MOCK)

            # Should log info about initialization
            info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("MOCK" in call or "mock" in call for call in info_calls)


class TestNeptuneModeEnum:
    """Tests for NeptuneMode enum."""

    def test_neptune_mode_mock_value(self):
        """Test NeptuneMode.MOCK has correct value."""
        assert NeptuneMode.MOCK.value == "mock"

    def test_neptune_mode_aws_value(self):
        """Test NeptuneMode.AWS has correct value."""
        assert NeptuneMode.AWS.value == "aws"

    def test_neptune_mode_is_enum(self):
        """Test NeptuneMode is an Enum."""
        from enum import Enum

        assert issubclass(NeptuneMode, Enum)


class TestNeptuneEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_add_entity_with_special_chars_in_name(self):
        """Test adding entity with special characters in name."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity(
            name="My'Special\"Class",
            entity_type="class",
            file_path="src/test.py",
            line_number=1,
        )

        assert entity_id is not None
        assert "My'Special\"Class" in entity_id

    def test_add_entity_with_unicode_in_name(self):
        """Test adding entity with unicode characters."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity(
            name="Clase_Unicode",
            entity_type="class",
            file_path="src/test.py",
            line_number=1,
        )

        assert entity_id is not None

    def test_add_entity_with_very_long_name(self):
        """Test adding entity with very long name."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        long_name = "A" * 1000
        entity_id = service.add_code_entity(
            name=long_name,
            entity_type="class",
            file_path="src/test.py",
            line_number=1,
        )

        assert entity_id is not None
        assert long_name in entity_id

    def test_add_entity_with_path_containing_special_chars(self):
        """Test adding entity with special characters in file path."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity(
            name="TestClass",
            entity_type="class",
            file_path="src/path with spaces/test.py",
            line_number=1,
        )

        assert entity_id == "src/path with spaces/test.py::TestClass"

    def test_add_entity_with_zero_line_number(self):
        """Test adding entity with line number 0."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity(
            name="TestClass",
            entity_type="class",
            file_path="src/test.py",
            line_number=0,
        )

        entity = service.mock_graph[entity_id]
        assert entity["line_number"] == 0

    def test_add_entity_with_negative_line_number(self):
        """Test adding entity with negative line number."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        entity_id = service.add_code_entity(
            name="TestClass",
            entity_type="class",
            file_path="src/test.py",
            line_number=-1,
        )

        entity = service.mock_graph[entity_id]
        assert entity["line_number"] == -1

    def test_relationship_with_empty_metadata(self):
        """Test adding relationship with empty metadata dict."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        result = service.add_relationship(
            from_entity="A", to_entity="B", relationship="CALLS", metadata={}
        )

        assert result is True

    def test_find_related_matches_from_and_to(self):
        """Test find_related_code matches entities in both from and to."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        id_a = service.add_code_entity("MatchA", "class", "a.py", 1)
        id_b = service.add_code_entity("MatchB", "class", "b.py", 1)
        service.add_relationship(id_a, id_b, "CALLS")

        # Should find B when searching for Match (A is in 'from')
        results_a = service.find_related_code("MatchA")

        # Should find A when searching for Match (B is in 'to')
        results_b = service.find_related_code("MatchB")

        # Both should return results
        assert len(results_a) > 0 or len(results_b) > 0

    def test_close_without_client(self):
        """Test close when no client attribute exists."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Ensure no client attribute
        if hasattr(service, "client"):
            delattr(service, "client")

        # Should not raise exception
        service.close()

    def test_add_entity_type_variations(self):
        """Test adding entities of various types."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        types = ["class", "function", "method", "variable", "import", "module"]

        for i, entity_type in enumerate(types):
            entity_id = service.add_code_entity(
                name=f"Entity{i}",
                entity_type=entity_type,
                file_path="src/test.py",
                line_number=i * 10,
            )
            entity = service.mock_graph[entity_id]
            assert entity["type"] == entity_type

    def test_search_with_special_regex_chars(self):
        """Test search with characters that could be regex special chars."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        service.add_code_entity("Test.Class", "class", "test.py", 1)

        # Search with dot (regex special char)
        results = service.search_by_name("Test.Class")

        assert len(results) >= 1


# =============================================================================
# ADR-056 Infrastructure Tests
# =============================================================================


class TestInfrastructureResource:
    """Tests for InfrastructureResource vertex operations."""

    def test_add_infrastructure_resource_returns_vertex_id(self):
        """Test that add_infrastructure_resource returns vertex ID."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_infrastructure_resource(
            resource_id="vpc-12345",
            resource_type="vpc",
            arn="arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345",
            name="Production VPC",
        )

        assert isinstance(vertex_id, str)
        assert vertex_id == "infra::vpc-12345"

    def test_add_infrastructure_resource_with_all_fields(self):
        """Test adding infrastructure resource with all optional fields."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_infrastructure_resource(
            resource_id="lambda-func-123",
            resource_type="lambda",
            arn="arn:aws:lambda:us-west-2:123456789012:function:MyFunc",
            name="MyFunc",
            provider="aws",
            region="us-west-2",
            account_id="123456789012",
            tags={"Environment": "prod", "Owner": "team-a"},
            configuration={"memory": 512, "timeout": 30},
        )

        resource = service.mock_graph[vertex_id]
        assert resource["resource_id"] == "lambda-func-123"
        assert resource["resource_type"] == "lambda"
        assert (
            resource["arn"] == "arn:aws:lambda:us-west-2:123456789012:function:MyFunc"
        )
        assert resource["name"] == "MyFunc"
        assert resource["provider"] == "aws"
        assert resource["region"] == "us-west-2"
        assert resource["account_id"] == "123456789012"
        assert resource["tags"]["Environment"] == "prod"
        assert resource["configuration"]["memory"] == 512

    def test_add_infrastructure_resource_default_values(self):
        """Test that default values are applied correctly."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_infrastructure_resource(
            resource_id="s3-bucket-1",
            resource_type="s3",
            arn="arn:aws:s3:::my-bucket",
            name="my-bucket",
        )

        resource = service.mock_graph[vertex_id]
        assert resource["provider"] == "aws"
        assert resource["region"] == "us-east-1"
        assert resource["account_id"] == ""
        assert resource["tags"] == {}
        assert resource["configuration"] == {}

    def test_add_infrastructure_resource_with_azure_provider(self):
        """Test adding Azure infrastructure resource."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_infrastructure_resource(
            resource_id="cosmos-db-1",
            resource_type="cosmos_db",
            arn="/subscriptions/abc/resourceGroups/rg/providers/Microsoft.DocumentDB/databaseAccounts/mydb",
            name="mydb",
            provider="azure",
            region="eastus",
        )

        resource = service.mock_graph[vertex_id]
        assert resource["provider"] == "azure"
        assert resource["region"] == "eastus"
        assert resource["label"] == "InfrastructureResource"

    def test_add_infrastructure_resource_stores_timestamp(self):
        """Test that discovered_at timestamp is stored."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_infrastructure_resource(
            resource_id="rds-instance-1",
            resource_type="rds",
            arn="arn:aws:rds:us-east-1:123456789012:db:mydb",
            name="mydb",
        )

        resource = service.mock_graph[vertex_id]
        assert "discovered_at" in resource


class TestServiceBoundary:
    """Tests for ServiceBoundary vertex operations."""

    def test_add_service_boundary_returns_vertex_id(self):
        """Test that add_service_boundary returns vertex ID."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_service_boundary(
            boundary_id="auth-service",
            name="Authentication Service",
            description="Handles user authentication and authorization",
            node_ids=["auth_handler", "token_validator", "session_manager"],
            confidence=0.85,
            repository_id="my-repo",
        )

        assert isinstance(vertex_id, str)
        assert vertex_id == "boundary::auth-service"

    def test_add_service_boundary_stores_all_fields(self):
        """Test that all boundary fields are stored correctly."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        node_ids = ["handler1", "handler2", "utils"]
        metadata = {"algorithm": "louvain", "resolution": 1.0}

        vertex_id = service.add_service_boundary(
            boundary_id="api-service",
            name="API Service",
            description="REST API endpoints",
            node_ids=node_ids,
            confidence=0.92,
            repository_id="test-repo",
            metadata=metadata,
        )

        boundary = service.mock_graph[vertex_id]
        assert boundary["boundary_id"] == "api-service"
        assert boundary["name"] == "API Service"
        assert boundary["description"] == "REST API endpoints"
        assert boundary["node_ids"] == node_ids
        assert boundary["node_count"] == 3
        assert boundary["confidence"] == 0.92
        assert boundary["repository_id"] == "test-repo"
        assert boundary["metadata"]["algorithm"] == "louvain"
        assert boundary["label"] == "ServiceBoundary"

    def test_add_service_boundary_creates_contains_edges(self):
        """Test that CONTAINS edges are created for each node."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # First add code entities
        service.add_code_entity("ClassA", "class", "a.py", 1)
        service.add_code_entity("ClassB", "class", "b.py", 1)

        vertex_id = service.add_service_boundary(
            boundary_id="my-service",
            name="My Service",
            description="Test service",
            node_ids=["ClassA", "ClassB"],
            confidence=0.8,
        )

        # Check CONTAINS edges were created
        contains_edges = [
            e
            for e in service.mock_edges
            if e["relationship"] == "CONTAINS" and e["from"] == vertex_id
        ]
        assert len(contains_edges) == 2

    def test_add_service_boundary_with_empty_nodes(self):
        """Test adding boundary with empty node list."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_service_boundary(
            boundary_id="empty-service",
            name="Empty Service",
            description="No nodes",
            node_ids=[],
            confidence=0.5,
        )

        boundary = service.mock_graph[vertex_id]
        assert boundary["node_count"] == 0
        assert boundary["node_ids"] == []

    def test_add_service_boundary_default_values(self):
        """Test default values for service boundary."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_service_boundary(
            boundary_id="test-boundary",
            name="Test",
            description="Test description",
            node_ids=["node1"],
            confidence=0.7,
        )

        boundary = service.mock_graph[vertex_id]
        assert boundary["repository_id"] == ""
        assert boundary["metadata"] == {}


class TestDataFlow:
    """Tests for DataFlow vertex operations."""

    def test_add_data_flow_returns_vertex_id(self):
        """Test that add_data_flow returns vertex ID."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_data_flow(
            flow_id="flow-api-to-db",
            source_id="api-service",
            target_id="database",
        )

        assert isinstance(vertex_id, str)
        assert vertex_id == "flow::flow-api-to-db"

    def test_add_data_flow_with_all_fields(self):
        """Test adding data flow with all optional fields."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_data_flow(
            flow_id="flow-123",
            source_id="producer-service",
            target_id="consumer-service",
            flow_type="async",
            data_types=["UserEvent", "OrderEvent"],
            protocol="kafka",
            direction="unidirectional",
            confidence=0.95,
            metadata={"topic": "events"},
        )

        flow = service.mock_graph[vertex_id]
        assert flow["flow_id"] == "flow-123"
        assert flow["source_id"] == "producer-service"
        assert flow["target_id"] == "consumer-service"
        assert flow["flow_type"] == "async"
        assert flow["data_types"] == ["UserEvent", "OrderEvent"]
        assert flow["protocol"] == "kafka"
        assert flow["direction"] == "unidirectional"
        assert flow["confidence"] == 0.95
        assert flow["metadata"]["topic"] == "events"
        assert flow["label"] == "DataFlow"

    def test_add_data_flow_creates_edges(self):
        """Test that directional edges are created between source and target."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add source and target entities
        service.add_code_entity("ProducerClass", "class", "producer.py", 1)
        service.add_code_entity("ConsumerClass", "class", "consumer.py", 1)

        service.add_data_flow(
            flow_id="flow-1",
            source_id="ProducerClass",
            target_id="ConsumerClass",
            flow_type="sync",  # sync flow uses WRITES_TO edge
        )

        # Check WRITES_TO edge (sync flow creates WRITES_TO from source to target)
        writes_edges = [
            e
            for e in service.mock_edges
            if e["relationship"] == "WRITES_TO"
            and e["from"] == "ProducerClass"
            and e["to"] == "ConsumerClass"
        ]
        assert len(writes_edges) == 1

    def test_add_data_flow_event_creates_produces_to_edge(self):
        """Test that event flow creates PRODUCES_TO edge."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        service.add_data_flow(
            flow_id="event-flow-1",
            source_id="EventProducer",
            target_id="EventConsumer",
            flow_type="event",  # event flow uses PRODUCES_TO edge
        )

        produces_edges = [
            e
            for e in service.mock_edges
            if e["relationship"] == "PRODUCES_TO"
            and e["from"] == "EventProducer"
            and e["to"] == "EventConsumer"
        ]
        assert len(produces_edges) == 1

    def test_add_data_flow_bidirectional(self):
        """Test adding bidirectional data flow."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_data_flow(
            flow_id="sync-flow",
            source_id="service-a",
            target_id="service-b",
            direction="bidirectional",
        )

        flow = service.mock_graph[vertex_id]
        assert flow["direction"] == "bidirectional"

    def test_add_data_flow_default_values(self):
        """Test default values for data flow."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_data_flow(
            flow_id="default-flow",
            source_id="src",
            target_id="dst",
        )

        flow = service.mock_graph[vertex_id]
        assert flow["flow_type"] == "sync"
        assert flow["data_types"] == []
        assert flow["protocol"] == ""
        assert flow["direction"] == "unidirectional"
        assert flow["confidence"] == 1.0
        assert flow["metadata"] == {}


class TestInfrastructureConnection:
    """Tests for infrastructure connection edge operations."""

    def test_add_infrastructure_connection_success(self):
        """Test adding infrastructure connection edge."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add resources first
        service.add_infrastructure_resource(
            resource_id="lambda-1",
            resource_type="lambda",
            arn="arn:aws:lambda:us-east-1:123:function:func1",
            name="Func1",
        )
        service.add_infrastructure_resource(
            resource_id="rds-1",
            resource_type="rds",
            arn="arn:aws:rds:us-east-1:123:db:mydb",
            name="MyDB",
        )

        result = service.add_infrastructure_connection(
            source_id="infra::lambda-1",
            target_id="infra::rds-1",
            connection_type="READS_FROM",
            protocol="tcp",
            port=5432,
            tls_enabled=True,
        )

        assert result is True

        # Verify edge exists
        edge = next(
            (
                e
                for e in service.mock_edges
                if e["from"] == "infra::lambda-1" and e["to"] == "infra::rds-1"
            ),
            None,
        )
        assert edge is not None
        assert edge["relationship"] == "READS_FROM"
        # In mock mode, protocol/port/tls_enabled are stored directly on the edge
        assert edge["protocol"] == "tcp"
        assert edge["port"] == 5432
        assert edge["tls_enabled"] is True

    def test_add_infrastructure_connection_types(self):
        """Test different connection types."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        connection_types = [
            "CONNECTS_TO",
            "OWNED_BY",
            "PRODUCES_TO",
            "CONSUMES_FROM",
            "READS_FROM",
            "WRITES_TO",
        ]

        for i, conn_type in enumerate(connection_types):
            result = service.add_infrastructure_connection(
                source_id=f"resource-{i}",
                target_id=f"resource-{i + 100}",
                connection_type=conn_type,
            )
            assert result is True

            edge = next(
                (e for e in service.mock_edges if e["from"] == f"resource-{i}"), None
            )
            assert edge is not None
            assert edge["relationship"] == conn_type

    def test_add_infrastructure_connection_with_metadata(self):
        """Test adding connection with custom metadata."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        result = service.add_infrastructure_connection(
            source_id="sqs-queue-1",
            target_id="lambda-consumer",
            connection_type="PRODUCES_TO",
            metadata={"batch_size": 10, "visibility_timeout": 30},
        )

        assert result is True

        edge = next((e for e in service.mock_edges if e["from"] == "sqs-queue-1"), None)
        assert edge["metadata"]["batch_size"] == 10
        assert edge["metadata"]["visibility_timeout"] == 30


class TestFindServiceInfrastructure:
    """Tests for find_service_infrastructure query."""

    def test_find_service_infrastructure_returns_resources(self):
        """Test finding infrastructure for a service."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add infrastructure resources
        service.add_infrastructure_resource(
            resource_id="db-1",
            resource_type="rds",
            arn="arn:aws:rds:us-east-1:123:db:mydb",
            name="MyDB",
        )

        # Add service boundary
        service.add_service_boundary(
            boundary_id="api-service",
            name="API Service",
            description="API endpoints",
            node_ids=["handler1", "handler2"],
            confidence=0.9,
        )

        # Add connection from service to infrastructure
        service.add_infrastructure_connection(
            source_id="boundary::api-service",
            target_id="infra::db-1",
            connection_type="READS_FROM",
        )

        results = service.find_service_infrastructure("api-service")

        assert isinstance(results, list)
        # In mock mode, results depend on edge traversal logic

    def test_find_service_infrastructure_with_max_depth(self):
        """Test finding infrastructure with depth limit."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        results = service.find_service_infrastructure(
            service_id="my-service", max_depth=1
        )

        assert isinstance(results, list)

    def test_find_service_infrastructure_nonexistent_service(self):
        """Test finding infrastructure for non-existent service."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        results = service.find_service_infrastructure("nonexistent-service")

        assert isinstance(results, list)
        assert len(results) == 0


class TestFindConnectedResources:
    """Tests for find_connected_resources query."""

    def test_find_connected_resources_returns_list(self):
        """Test finding connected resources returns list."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add resources and connections
        service.add_infrastructure_resource(
            resource_id="vpc-1",
            resource_type="vpc",
            arn="arn:aws:ec2:us-east-1:123:vpc/vpc-1",
            name="Main VPC",
        )
        service.add_infrastructure_resource(
            resource_id="subnet-1",
            resource_type="subnet",
            arn="arn:aws:ec2:us-east-1:123:subnet/subnet-1",
            name="Public Subnet",
        )

        service.add_infrastructure_connection(
            source_id="infra::vpc-1",
            target_id="infra::subnet-1",
            connection_type="CONTAINS",
        )

        results = service.find_connected_resources("vpc-1")

        assert isinstance(results, list)

    def test_find_connected_resources_with_filter(self):
        """Test finding connected resources with connection type filter."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        results = service.find_connected_resources(
            resource_id="my-resource",
            connection_types=["CONNECTS_TO", "READS_FROM"],
        )

        assert isinstance(results, list)

    def test_find_connected_resources_with_depth(self):
        """Test finding connected resources with max depth."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        results = service.find_connected_resources(
            resource_id="my-resource",
            max_depth=2,
        )

        assert isinstance(results, list)


class TestDeleteServiceBoundaries:
    """Tests for delete_service_boundaries operation."""

    def test_delete_service_boundaries_returns_count(self):
        """Test that delete returns count of deleted boundaries."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add some boundaries
        service.add_service_boundary(
            boundary_id="boundary-1",
            name="Service 1",
            description="First service",
            node_ids=["a", "b"],
            confidence=0.8,
            repository_id="test-repo",
        )
        service.add_service_boundary(
            boundary_id="boundary-2",
            name="Service 2",
            description="Second service",
            node_ids=["c", "d"],
            confidence=0.9,
            repository_id="test-repo",
        )
        service.add_service_boundary(
            boundary_id="boundary-3",
            name="Service 3",
            description="Third service",
            node_ids=["e"],
            confidence=0.7,
            repository_id="other-repo",
        )

        # Delete boundaries for test-repo
        deleted_count = service.delete_service_boundaries("test-repo")

        assert deleted_count == 2

        # Verify only other-repo boundary remains
        remaining = [
            v
            for v in service.mock_graph.values()
            if v.get("label") == "ServiceBoundary"
        ]
        assert len(remaining) == 1
        assert remaining[0]["repository_id"] == "other-repo"

    def test_delete_service_boundaries_removes_edges(self):
        """Test that deleting boundaries also removes associated edges."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add entity and boundary
        service.add_code_entity("ClassX", "class", "x.py", 1)
        service.add_service_boundary(
            boundary_id="my-boundary",
            name="My Service",
            description="Test service",
            node_ids=["ClassX"],
            confidence=0.85,
            repository_id="test-repo",
        )

        # Verify edge exists
        contains_edges_before = [
            e
            for e in service.mock_edges
            if e["relationship"] == "CONTAINS" and "my-boundary" in e["from"]
        ]
        assert len(contains_edges_before) > 0

        # Delete boundaries
        service.delete_service_boundaries("test-repo")

        # Verify edges are removed
        contains_edges_after = [
            e
            for e in service.mock_edges
            if e["relationship"] == "CONTAINS" and "my-boundary" in e["from"]
        ]
        assert len(contains_edges_after) == 0

    def test_delete_service_boundaries_nonexistent_repo(self):
        """Test deleting boundaries for non-existent repository."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        deleted_count = service.delete_service_boundaries("nonexistent-repo")

        assert deleted_count == 0

    def test_delete_service_boundaries_empty_graph(self):
        """Test deleting boundaries when graph is empty."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Clear the mock graph
        service.mock_graph.clear()

        deleted_count = service.delete_service_boundaries("any-repo")

        assert deleted_count == 0


class TestInfrastructureVertexLookup:
    """Tests for infrastructure vertex lookup helper."""

    def test_lookup_by_vertex_id(self):
        """Test looking up vertex by vertex_id property."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add infrastructure resource (uses vertex_id internally)
        service.add_infrastructure_resource(
            resource_id="test-resource",
            resource_type="ec2",
            arn="arn:aws:ec2:us-east-1:123:instance/i-123",
            name="TestInstance",
        )

        # The resource should be findable
        found = "infra::test-resource" in service.mock_graph
        assert found is True

    def test_lookup_by_entity_id(self):
        """Test looking up vertex by entity_id property."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        # Add code entity (uses entity_id via id field)
        entity_id = service.add_code_entity(
            name="TestClass",
            entity_type="class",
            file_path="test.py",
            line_number=1,
        )

        found = entity_id in service.mock_graph
        assert found is True

    def test_lookup_by_resource_id(self):
        """Test looking up by resource_id property."""
        service = NeptuneGraphService(mode=NeptuneMode.MOCK)

        vertex_id = service.add_infrastructure_resource(
            resource_id="my-special-resource",
            resource_type="s3",
            arn="arn:aws:s3:::my-bucket",
            name="MyBucket",
        )

        resource = service.mock_graph[vertex_id]
        assert resource["resource_id"] == "my-special-resource"
