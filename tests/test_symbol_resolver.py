"""Tests for ADR-090 Phase 4a Tier 1 deterministic symbol resolver."""

from __future__ import annotations

import pytest

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship
from src.services.graph.edge_labels import EdgeLabel
from src.services.graph.fqn import compute_fqn
from src.services.graph.symbol_resolver import (
    ResolutionStats,
    Tier1SymbolResolver,
)

REPO_ID = "owner/repo"


def _entity(
    name: str,
    kind: str,
    file_path: str,
    line: int = 1,
    parent_chain: tuple[str, ...] = (),
) -> CodeEntity:
    return CodeEntity(
        name=name,
        entity_type=kind,
        file_path=file_path,
        line_number=line,
        parent_chain=parent_chain,
        parent_entity=parent_chain[-1] if parent_chain else None,
    )


def _calls(
    source: str,
    target: str,
    file_path: str,
    parent_chain: tuple[str, ...] = (),
) -> CodeRelationship:
    return CodeRelationship(
        source_name=source,
        source_parent_chain=parent_chain,
        target_name=target,
        relationship=EdgeLabel.CALLS.value,
        properties={"call_site_line": 1},
        file_path=file_path,
    )


def _imports(
    local_binding: str, source_module: str, file_path: str
) -> CodeRelationship:
    return CodeRelationship(
        source_name=local_binding,
        source_parent_chain=(),
        target_name=source_module,
        relationship=EdgeLabel.IMPORTS.value,
        properties={"line": 1},
        file_path=file_path,
    )


@pytest.fixture
def resolver() -> Tier1SymbolResolver:
    return Tier1SymbolResolver()


class TestSameFileResolution:
    def test_call_resolves_to_sibling_in_same_file(self, resolver):
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/utils.py", line=5),
        ]
        relationships = [
            _calls("main", "helper", "myapp/utils.py"),
        ]
        resolved, stats = resolver.resolve(entities, relationships, REPO_ID)
        expected = compute_fqn(
            name="helper",
            kind="function",
            file_path="myapp/utils.py",
            repo_id=REPO_ID,
        )
        assert resolved[0].target_fqn == expected
        assert stats.same_file_resolved == 1

    def test_ambiguous_same_file_match_skipped(self, resolver):
        """Two same-file entities with the same name are skipped."""
        entities = [
            _entity("verify", "method", "auth.py", line=5, parent_chain=("User",)),
            _entity("verify", "method", "auth.py", line=10, parent_chain=("User",)),
            _entity("driver", "function", "auth.py", line=15),
        ]
        relationships = [_calls("driver", "verify", "auth.py")]
        resolved, stats = resolver.resolve(entities, relationships, REPO_ID)
        assert resolved[0].target_fqn is None
        assert stats.ambiguous_skipped == 1


class TestDirectImportResolution:
    def test_from_import_resolves_to_target_module(self, resolver):
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        relationships = [
            _imports("helper", "myapp.utils", "myapp/runner.py"),
            _calls("main", "helper", "myapp/runner.py"),
        ]
        resolved, stats = resolver.resolve(entities, relationships, REPO_ID)
        expected = compute_fqn(
            name="helper",
            kind="function",
            file_path="myapp/utils.py",
            repo_id=REPO_ID,
        )
        # The CALLS edge is at index 1 (after the IMPORTS edge).
        calls_rel = next(r for r in resolved if r.relationship == EdgeLabel.CALLS.value)
        assert calls_rel.target_fqn == expected
        assert stats.direct_import_resolved == 1

    def test_unimported_name_remains_unresolved(self, resolver):
        entities = [_entity("main", "function", "myapp/runner.py")]
        relationships = [_calls("main", "external_thing", "myapp/runner.py")]
        resolved, stats = resolver.resolve(entities, relationships, REPO_ID)
        assert resolved[0].target_fqn is None
        assert stats.unresolved == 1

    def test_imported_module_not_in_repo_remains_unresolved(self, resolver):
        """``from boto3 import client`` -> boto3 is cross-package."""
        entities = [_entity("main", "function", "myapp/runner.py")]
        relationships = [
            _imports("client", "boto3", "myapp/runner.py"),
            _calls("main", "client", "myapp/runner.py"),
        ]
        resolved, stats = resolver.resolve(entities, relationships, REPO_ID)
        calls_rel = next(r for r in resolved if r.relationship == EdgeLabel.CALLS.value)
        assert calls_rel.target_fqn is None
        assert stats.unresolved == 1


class TestModulePrefixResolution:
    def test_module_alias_call_resolves(self, resolver):
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        relationships = [
            _imports("utils", "myapp.utils", "myapp/runner.py"),
            _calls("main", "utils.helper", "myapp/runner.py"),
        ]
        resolved, stats = resolver.resolve(entities, relationships, REPO_ID)
        expected = compute_fqn(
            name="helper",
            kind="function",
            file_path="myapp/utils.py",
            repo_id=REPO_ID,
        )
        calls_rel = next(r for r in resolved if r.relationship == EdgeLabel.CALLS.value)
        assert calls_rel.target_fqn == expected
        assert stats.module_prefix_resolved == 1

    def test_self_target_not_resolved_in_tier1(self, resolver):
        """``self.method`` requires class hierarchy traversal (Tier 2)."""
        entities = [
            _entity("App", "class", "app.py"),
            _entity("run", "method", "app.py", parent_chain=("App",)),
            _entity("handle", "method", "app.py", parent_chain=("App",)),
        ]
        relationships = [
            _calls("run", "self.handle", "app.py", parent_chain=("App",)),
        ]
        resolved, stats = resolver.resolve(entities, relationships, REPO_ID)
        assert resolved[0].target_fqn is None
        assert stats.unresolved == 1


class TestPassThrough:
    def test_inherits_relationships_unchanged(self, resolver):
        entities = [_entity("Derived", "class", "x.py")]
        relationships = [
            CodeRelationship(
                source_name="Derived",
                source_parent_chain=(),
                target_name="Base",
                relationship=EdgeLabel.INHERITS.value,
                file_path="x.py",
            )
        ]
        resolved, stats = resolver.resolve(entities, relationships, REPO_ID)
        assert resolved[0].target_fqn is None  # Tier 1 does not resolve INHERITS
        assert stats.skipped_non_calls == 1

    def test_imports_relationships_unchanged(self, resolver):
        entities = [_entity("driver", "function", "x.py")]
        relationships = [_imports("Foo", "myapp.foo", "x.py")]
        resolved, stats = resolver.resolve(entities, relationships, REPO_ID)
        assert resolved[0].target_fqn is None
        assert stats.skipped_non_calls == 1


class TestImmutability:
    def test_input_relationships_not_mutated(self, resolver):
        entities = [
            _entity("helper", "function", "u.py"),
            _entity("main", "function", "u.py"),
        ]
        original_rel = _calls("main", "helper", "u.py")
        resolved, _ = resolver.resolve(entities, [original_rel], REPO_ID)
        # Input was not mutated.
        assert original_rel.target_fqn is None
        # Output has the resolved FQN on a fresh record.
        assert resolved[0] is not original_rel
        assert resolved[0].target_fqn is not None


class TestStatsTelemetry:
    def test_stats_account_for_every_relationship(self, resolver):
        entities = [
            _entity("helper", "function", "u.py"),
            _entity("main", "function", "u.py"),
        ]
        relationships = [
            _calls("main", "helper", "u.py"),  # same-file
            _calls("main", "missing", "u.py"),  # unresolved
            CodeRelationship(
                source_name="x",
                source_parent_chain=(),
                target_name="y",
                relationship=EdgeLabel.INHERITS.value,
                file_path="u.py",
            ),  # skipped (non-CALLS)
        ]
        resolved, stats = resolver.resolve(entities, relationships, REPO_ID)
        assert stats.relationships_seen == 3
        assert stats.calls_seen == 2
        assert stats.same_file_resolved == 1
        assert stats.unresolved == 1
        assert stats.skipped_non_calls == 1
        assert len(resolved) == 3

    def test_stats_dataclass_has_default_zeros(self):
        s = ResolutionStats()
        assert s.relationships_seen == 0
        assert s.calls_seen == 0
        assert s.same_file_resolved == 0
        assert s.direct_import_resolved == 0
        assert s.module_prefix_resolved == 0
