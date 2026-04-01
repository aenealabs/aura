"""
Pytest fixtures for polyglot dependency graph service tests.
"""

import pytest

from src.services.polyglot import (
    CodeEntity,
    CodeRelationship,
    EntityType,
    Language,
    PolyglotConfig,
    PolyglotDependencyGraph,
    RelationType,
    reset_dependency_graph,
    reset_polyglot_config,
    reset_shard_router,
    set_polyglot_config,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before each test."""
    reset_polyglot_config()
    reset_dependency_graph()
    reset_shard_router()
    yield
    reset_polyglot_config()
    reset_dependency_graph()
    reset_shard_router()


@pytest.fixture
def test_config():
    """Create test configuration."""
    config = PolyglotConfig.for_testing()
    set_polyglot_config(config)
    return config


@pytest.fixture
def graph(test_config):
    """Create dependency graph."""
    return PolyglotDependencyGraph(test_config)


@pytest.fixture
def sample_entity():
    """Create sample code entity."""
    return CodeEntity(
        id="entity-001",
        type=EntityType.CLASS,
        name="UserService",
        qualified_name="src.services.UserService",
        language=Language.PYTHON,
        file_path="src/services/user_service.py",
        line_start=10,
        line_end=100,
    )


@pytest.fixture
def sample_entities():
    """Create multiple sample entities."""
    return [
        CodeEntity(
            id="entity-001",
            type=EntityType.CLASS,
            name="UserService",
            qualified_name="src.services.UserService",
            language=Language.PYTHON,
            file_path="src/services/user_service.py",
            line_start=10,
            line_end=100,
        ),
        CodeEntity(
            id="entity-002",
            type=EntityType.CLASS,
            name="AuthService",
            qualified_name="src.services.AuthService",
            language=Language.PYTHON,
            file_path="src/services/auth_service.py",
            line_start=10,
            line_end=80,
        ),
        CodeEntity(
            id="entity-003",
            type=EntityType.FUNCTION,
            name="validate_token",
            qualified_name="src.utils.validate_token",
            language=Language.PYTHON,
            file_path="src/utils/auth.py",
            line_start=5,
            line_end=20,
        ),
    ]


@pytest.fixture
def sample_relationship():
    """Create sample relationship."""
    return CodeRelationship(
        id="rel-001",
        source_id="entity-001",
        target_id="entity-002",
        type=RelationType.IMPORTS,
        weight=1.0,
    )
