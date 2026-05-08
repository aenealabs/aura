"""Tests for ADR-090 Phase 4b Tier 2 symbol resolvers."""

from __future__ import annotations

import json

import pytest

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship
from src.services.graph.edge_labels import EdgeLabel
from src.services.graph.fqn import compute_fqn
from src.services.graph.symbol_resolver_tier2 import (
    Tier2PyrightBackend,
    Tier2SelfMethodResolver,
    Tier2Stats,
    Tier2SymbolResolver,
    _encode_lsp_payload,
    _parse_content_length,
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
    line: int = 1,
) -> CodeRelationship:
    return CodeRelationship(
        source_name=source,
        source_parent_chain=parent_chain,
        target_name=target,
        relationship=EdgeLabel.CALLS.value,
        properties={"call_site_line": line},
        file_path=file_path,
    )


def _inherits(
    source_class: str,
    base_class: str,
    file_path: str,
) -> CodeRelationship:
    return CodeRelationship(
        source_name=source_class,
        source_parent_chain=(),
        target_name=base_class,
        relationship=EdgeLabel.INHERITS.value,
        file_path=file_path,
    )


# -- Self-method resolver -----------------------------------------------


class TestSelfMethodResolverIntraClass:
    def test_self_call_to_sibling_method(self):
        entities = [
            _entity("App", "class", "app.py"),
            _entity("run", "method", "app.py", line=5, parent_chain=("App",)),
            _entity("handle", "method", "app.py", line=10, parent_chain=("App",)),
        ]
        relationships = [_calls("run", "self.handle", "app.py", parent_chain=("App",))]
        resolver = Tier2SelfMethodResolver()
        stats = Tier2Stats()
        out = resolver.resolve(entities, relationships, REPO_ID, stats)
        expected = compute_fqn(
            name="handle",
            kind="method",
            file_path="app.py",
            repo_id=REPO_ID,
            parent_chain=("App",),
        )
        assert out[0].target_fqn == expected
        assert stats.self_method_resolved == 1
        assert stats.self_method_via_inheritance == 0

    def test_this_keyword_in_javascript_resolves(self):
        entities = [
            _entity("App", "class", "app.js"),
            _entity("run", "method", "app.js", line=5, parent_chain=("App",)),
            _entity("handle", "method", "app.js", line=10, parent_chain=("App",)),
        ]
        relationships = [_calls("run", "this.handle", "app.js", parent_chain=("App",))]
        resolver = Tier2SelfMethodResolver()
        stats = Tier2Stats()
        out = resolver.resolve(entities, relationships, REPO_ID, stats)
        assert out[0].target_fqn is not None
        assert stats.self_method_resolved == 1

    def test_unresolvable_self_call_passes_through(self):
        entities = [
            _entity("App", "class", "app.py"),
            _entity("run", "method", "app.py", line=5, parent_chain=("App",)),
        ]
        # ``self.missing`` does not exist on App or any base.
        relationships = [_calls("run", "self.missing", "app.py", parent_chain=("App",))]
        resolver = Tier2SelfMethodResolver()
        stats = Tier2Stats()
        out = resolver.resolve(entities, relationships, REPO_ID, stats)
        assert out[0].target_fqn is None
        assert stats.self_method_resolved == 0

    def test_deeply_nested_chain_not_resolved_in_phase_4b(self):
        """``self.foo.bar`` is two-step; deferred to Tier 3."""
        entities = [
            _entity("App", "class", "app.py"),
            _entity("run", "method", "app.py", line=5, parent_chain=("App",)),
        ]
        relationships = [
            _calls(
                "run",
                "self.collaborator.do_thing",
                "app.py",
                parent_chain=("App",),
            )
        ]
        resolver = Tier2SelfMethodResolver()
        stats = Tier2Stats()
        out = resolver.resolve(entities, relationships, REPO_ID, stats)
        assert out[0].target_fqn is None


class TestSelfMethodResolverInheritance:
    def test_inherited_method_resolves_via_inherits_edge(self):
        entities = [
            _entity("Base", "class", "x.py"),
            _entity("shared", "method", "x.py", line=5, parent_chain=("Base",)),
            _entity("App", "class", "x.py", line=20),
            _entity("run", "method", "x.py", line=25, parent_chain=("App",)),
        ]
        relationships = [
            _calls("run", "self.shared", "x.py", parent_chain=("App",)),
            _inherits("App", "Base", "x.py"),
        ]
        resolver = Tier2SelfMethodResolver()
        stats = Tier2Stats()
        out = resolver.resolve(entities, relationships, REPO_ID, stats)
        # The CALLS edge is at index 0 (inputs preserved in order).
        calls_rel = next(r for r in out if r.relationship == EdgeLabel.CALLS.value)
        expected = compute_fqn(
            name="shared",
            kind="method",
            file_path="x.py",
            repo_id=REPO_ID,
            parent_chain=("Base",),
        )
        assert calls_rel.target_fqn == expected
        assert stats.self_method_via_inheritance == 1

    def test_multiple_inheritance_with_unique_match_resolves(self):
        entities = [
            _entity("Mix", "class", "x.py"),
            _entity("shared", "method", "x.py", line=5, parent_chain=("Mix",)),
            _entity("Base", "class", "x.py", line=15),
            _entity("App", "class", "x.py", line=25),
            _entity("run", "method", "x.py", line=30, parent_chain=("App",)),
        ]
        relationships = [
            _calls("run", "self.shared", "x.py", parent_chain=("App",)),
            _inherits("App", "Mix", "x.py"),
            _inherits("App", "Base", "x.py"),
        ]
        resolver = Tier2SelfMethodResolver()
        stats = Tier2Stats()
        out = resolver.resolve(entities, relationships, REPO_ID, stats)
        calls_rel = next(r for r in out if r.relationship == EdgeLabel.CALLS.value)
        # Only Mix declares ``shared``; resolution unique.
        assert calls_rel.target_fqn is not None
        assert stats.self_method_via_inheritance == 1

    def test_multiple_inheritance_with_ambiguous_match_skipped(self):
        entities = [
            _entity("Mix", "class", "x.py"),
            _entity("shared", "method", "x.py", line=5, parent_chain=("Mix",)),
            _entity("Base", "class", "x.py", line=15),
            _entity("shared", "method", "x.py", line=20, parent_chain=("Base",)),
            _entity("App", "class", "x.py", line=25),
            _entity("run", "method", "x.py", line=30, parent_chain=("App",)),
        ]
        relationships = [
            _calls("run", "self.shared", "x.py", parent_chain=("App",)),
            _inherits("App", "Mix", "x.py"),
            _inherits("App", "Base", "x.py"),
        ]
        resolver = Tier2SelfMethodResolver()
        stats = Tier2Stats()
        out = resolver.resolve(entities, relationships, REPO_ID, stats)
        calls_rel = next(r for r in out if r.relationship == EdgeLabel.CALLS.value)
        assert calls_rel.target_fqn is None
        # Tier 2 stays conservative under ambiguity.
        assert stats.self_method_via_inheritance == 0


class TestSelfMethodResolverPassthrough:
    def test_non_self_calls_unchanged(self):
        entities = [_entity("App", "class", "x.py")]
        relationships = [_calls("App", "external", "x.py")]
        resolver = Tier2SelfMethodResolver()
        stats = Tier2Stats()
        out = resolver.resolve(entities, relationships, REPO_ID, stats)
        assert out[0] is relationships[0]
        assert stats.candidates_considered == 0

    def test_inherits_relationships_unchanged(self):
        relationships = [_inherits("Derived", "Base", "x.py")]
        resolver = Tier2SelfMethodResolver()
        stats = Tier2Stats()
        out = resolver.resolve([], relationships, REPO_ID, stats)
        assert out[0] is relationships[0]


# -- Pyright backend (soft-dependency surface) --------------------------


class TestPyrightBackendSoftDependency:
    def test_no_pyright_binary_means_no_op(self, monkeypatch):
        # Force discovery to return None.
        monkeypatch.setattr(
            "src.services.graph.symbol_resolver_tier2.shutil.which",
            lambda _: None,
        )
        monkeypatch.delenv("AURA_PYRIGHT_PATH", raising=False)
        backend = Tier2PyrightBackend()
        assert backend.available is False

        relationships = [_calls("run", "obj.handle", "x.py")]
        stats = Tier2Stats()
        out = backend.resolve(
            [], relationships, repo_root="/tmp", repo_id=REPO_ID, stats=stats
        )
        assert out is relationships  # unchanged
        assert stats.pyright_unavailable == 1
        assert stats.pyright_resolved == 0

    def test_no_repo_root_means_no_op(self):
        backend = Tier2PyrightBackend(pyright_path="/fake/pyright")
        relationships = [_calls("run", "obj.handle", "x.py")]
        stats = Tier2Stats()
        out = backend.resolve(
            [], relationships, repo_root=None, repo_id=REPO_ID, stats=stats
        )
        assert out is relationships

    def test_pyright_path_env_var_picked_up(self, monkeypatch, tmp_path):
        fake = tmp_path / "fake-pyright"
        fake.write_text("#!/bin/sh\nexit 0\n")
        fake.chmod(0o755)
        monkeypatch.setenv("AURA_PYRIGHT_PATH", str(fake))
        backend = Tier2PyrightBackend()
        assert backend.pyright_path == str(fake)
        assert backend.available is True


class TestLSPFraming:
    def test_encode_includes_content_length(self):
        encoded = _encode_lsp_payload({"jsonrpc": "2.0", "id": 1, "method": "x"})
        assert encoded.startswith(b"Content-Length: ")
        # Body is appended after CRLFCRLF.
        header, _, body = encoded.partition(b"\r\n\r\n")
        body_obj = json.loads(body)
        assert body_obj["method"] == "x"
        # Content-Length value matches body length.
        announced = int(header.split(b":", 1)[1].strip())
        assert announced == len(body)

    def test_parse_content_length_extracts_int(self):
        header = b"Content-Length: 42\r\nContent-Type: application/json\r\n"
        assert _parse_content_length(header) == 42

    def test_parse_content_length_returns_none_on_missing(self):
        header = b"Content-Type: application/json\r\n"
        assert _parse_content_length(header) is None

    def test_parse_content_length_returns_none_on_bad_value(self):
        header = b"Content-Length: not-a-number\r\n"
        assert _parse_content_length(header) is None


# -- Composer -----------------------------------------------------------


class TestTier2Composition:
    def test_composer_runs_self_method_then_pyright(self, monkeypatch):
        # Force Pyright unavailable so the composer exits with just
        # the self-method resolver's output.
        monkeypatch.setattr(
            "src.services.graph.symbol_resolver_tier2.shutil.which",
            lambda _: None,
        )
        monkeypatch.delenv("AURA_PYRIGHT_PATH", raising=False)

        entities = [
            _entity("App", "class", "x.py"),
            _entity("run", "method", "x.py", line=5, parent_chain=("App",)),
            _entity("handle", "method", "x.py", line=10, parent_chain=("App",)),
        ]
        relationships = [_calls("run", "self.handle", "x.py", parent_chain=("App",))]
        composer = Tier2SymbolResolver()
        out, stats = composer.resolve(entities, relationships, REPO_ID)
        assert out[0].target_fqn is not None
        assert stats.self_method_resolved == 1
        # Pyright was unavailable; the composer counted the still-
        # unresolved set after both stages -- which here is 0 because
        # the deterministic stage already resolved.
        assert stats.still_unresolved == 0

    def test_composer_reports_still_unresolved_when_no_tier_can_match(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "src.services.graph.symbol_resolver_tier2.shutil.which",
            lambda _: None,
        )
        monkeypatch.delenv("AURA_PYRIGHT_PATH", raising=False)

        entities = [_entity("App", "class", "x.py")]
        relationships = [_calls("App", "external_func", "x.py")]
        composer = Tier2SymbolResolver()
        out, stats = composer.resolve(entities, relationships, REPO_ID)
        assert out[0].target_fqn is None
        assert stats.still_unresolved == 1

    def test_composer_pass_through_for_non_calls(self, monkeypatch):
        monkeypatch.setattr(
            "src.services.graph.symbol_resolver_tier2.shutil.which",
            lambda _: None,
        )
        monkeypatch.delenv("AURA_PYRIGHT_PATH", raising=False)
        relationships = [_inherits("Derived", "Base", "x.py")]
        composer = Tier2SymbolResolver()
        out, stats = composer.resolve([], relationships, REPO_ID)
        assert out[0] is relationships[0]
        # INHERITS edges are never CALLS, so no pyright_unavailable counts.
        assert stats.pyright_unavailable == 0


class TestStatsTelemetry:
    def test_default_zeros(self):
        s = Tier2Stats()
        assert s.candidates_considered == 0
        assert s.self_method_resolved == 0
        assert s.self_method_via_inheritance == 0
        assert s.pyright_attempted == 0
        assert s.pyright_resolved == 0
        assert s.pyright_timed_out == 0
        assert s.pyright_unavailable == 0
        assert s.still_unresolved == 0
