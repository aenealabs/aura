"""Tests for ADR-090 Phase 1 migration script.

The migration must be idempotent, resumable, and correctly disambiguate
overload-style collisions by line_number ordering.
"""

from __future__ import annotations

import pytest

from scripts.migrate_entity_ids_adr090 import migrate
from src.services.neptune_graph_service import NeptuneGraphService, NeptuneMode


@pytest.fixture
def service():
    """Mock NeptuneGraphService with the default seed data cleared.

    NeptuneGraphService._init_mock_mode pre-populates mock_graph with
    sample fixtures that lack repository metadata; they would skew the
    migration scan counts. The fixture starts each test from an empty
    graph.
    """
    svc = NeptuneGraphService(mode=NeptuneMode.MOCK)
    svc.mock_graph.clear()
    svc.mock_edges.clear()
    return svc


def _seed(
    svc: NeptuneGraphService,
    *,
    name: str,
    entity_type: str,
    file_path: str,
    line_number: int,
    repo: str = "owner/repo",
    parent: str | None = None,
) -> str:
    """Insert a pre-Phase-1-shape entity directly into the mock graph.

    Bypasses ``add_code_entity`` for two reasons: (1) the auto-FQN
    write path it now performs would short-circuit the migration we
    are trying to exercise, and (2) ``add_code_entity``'s legacy
    entity_id (``{file_path}::{name}``) collides on overload-style
    callers — exactly the bug the migration exists to fix. Tests that
    simulate multiple distinct vertices in a collision bucket need
    unique synthetic keys to express that state.
    """
    synthetic_key = f"{file_path}::{name}::L{line_number}"
    svc.mock_graph[synthetic_key] = {
        "id": synthetic_key,
        "entity_id": synthetic_key,
        "name": name,
        "type": entity_type,
        "file_path": file_path,
        "line_number": line_number,
        "parent": parent,
        "metadata": {"repository": repo},
    }
    return synthetic_key


class TestBasicMigration:
    def test_assigns_fqn_to_unmigrated_entity(self, service):
        eid = _seed(
            service,
            name="App",
            entity_type="class",
            file_path="src/api.py",
            line_number=10,
        )
        stats = migrate(service)
        assert stats.scanned == 1
        assert stats.migrated == 1
        assert service.mock_graph[eid]["fqn"] == "python:owner/repo:api:App#class"

    def test_skips_already_migrated(self, service):
        _seed(
            service,
            name="App",
            entity_type="class",
            file_path="src/api.py",
            line_number=10,
        )
        first = migrate(service)
        second = migrate(service)
        assert first.migrated == 1
        assert second.migrated == 0
        assert second.skipped_already_migrated == 1

    def test_skips_entity_without_repo_metadata(self, service):
        # Add directly to mock_graph without repository metadata
        service.mock_graph["bare::Entity"] = {
            "id": "bare::Entity",
            "name": "Entity",
            "type": "class",
            "file_path": "bare.py",
            "line_number": 1,
            "metadata": {},  # no repository
        }
        stats = migrate(service)
        assert stats.skipped_missing_repo == 1
        assert "fqn" not in service.mock_graph["bare::Entity"]


class TestRepoFiltering:
    def test_only_migrates_specified_repo(self, service):
        a = _seed(
            service,
            name="A",
            entity_type="class",
            file_path="src/a.py",
            line_number=1,
            repo="org/repo-a",
        )
        b = _seed(
            service,
            name="B",
            entity_type="class",
            file_path="src/b.py",
            line_number=1,
            repo="org/repo-b",
        )
        stats = migrate(service, repo_filter="org/repo-a")
        assert stats.scanned == 1
        assert stats.migrated == 1
        assert "fqn" in service.mock_graph[a]
        assert "fqn" not in service.mock_graph[b]


class TestDisambiguation:
    def test_overload_assigned_by_line_order(self, service):
        """Two methods with same scope/name/kind: lower line gets no suffix."""
        first = _seed(
            service,
            name="verify",
            entity_type="method",
            file_path="src/auth.py",
            line_number=5,
            parent="User",
        )
        second = _seed(
            service,
            name="verify",
            entity_type="method",
            file_path="src/auth.py",
            line_number=20,
            parent="User",
        )
        third = _seed(
            service,
            name="verify",
            entity_type="method",
            file_path="src/auth.py",
            line_number=35,
            parent="User",
        )

        migrate(service)

        assert service.mock_graph[first]["fqn"].endswith("#method")
        assert service.mock_graph[second]["fqn"].endswith("@1")
        assert service.mock_graph[third]["fqn"].endswith("@2")

    def test_different_parents_do_not_collide(self, service):
        a = _seed(
            service,
            name="verify",
            entity_type="method",
            file_path="src/auth.py",
            line_number=5,
            parent="User",
        )
        b = _seed(
            service,
            name="verify",
            entity_type="method",
            file_path="src/auth.py",
            line_number=10,
            parent="Admin",
        )
        migrate(service)
        # Neither should be disambiguated.
        assert "@" not in service.mock_graph[a]["fqn"]
        assert "@" not in service.mock_graph[b]["fqn"]

    def test_assignment_is_stable_across_runs(self, service):
        """A re-run on a partially-migrated graph must produce identical FQNs."""
        first = _seed(
            service,
            name="verify",
            entity_type="method",
            file_path="src/auth.py",
            line_number=5,
            parent="User",
        )
        second = _seed(
            service,
            name="verify",
            entity_type="method",
            file_path="src/auth.py",
            line_number=20,
            parent="User",
        )

        migrate(service)
        first_fqn_initial = service.mock_graph[first]["fqn"]
        second_fqn_initial = service.mock_graph[second]["fqn"]

        # Add another entity to the same collision bucket and re-migrate.
        third = _seed(
            service,
            name="verify",
            entity_type="method",
            file_path="src/auth.py",
            line_number=35,
            parent="User",
        )
        migrate(service)

        # First two FQNs preserved (idempotency).
        assert service.mock_graph[first]["fqn"] == first_fqn_initial
        assert service.mock_graph[second]["fqn"] == second_fqn_initial
        # Third gets the next disambiguator.
        assert service.mock_graph[third]["fqn"].endswith("@2")


class TestDryRun:
    def test_dry_run_does_not_write(self, service):
        eid = _seed(
            service,
            name="App",
            entity_type="class",
            file_path="src/api.py",
            line_number=10,
        )
        stats = migrate(service, dry_run=True)
        assert stats.migrated == 1
        assert "fqn" not in service.mock_graph[eid]


class TestReadPathPreference:
    """get_entity_by_id prefers fqn over entity_id (mock-mode)."""

    def test_fqn_lookup_returns_record(self, service):
        eid = _seed(
            service,
            name="App",
            entity_type="class",
            file_path="src/api.py",
            line_number=10,
        )
        migrate(service)
        fqn = service.mock_graph[eid]["fqn"]
        result = service.get_entity_by_id(fqn)
        assert result is not None
        assert result["name"] == "App"

    def test_legacy_entity_id_still_works(self, service):
        eid = _seed(
            service,
            name="App",
            entity_type="class",
            file_path="src/api.py",
            line_number=10,
        )
        migrate(service)
        # Lookup by legacy entity_id is the dual-write fallback.
        result = service.get_entity_by_id(eid)
        assert result is not None
        assert result["name"] == "App"
